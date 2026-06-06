"""
LLM Adapter — 统一 LLM 接口实现
支持: mimo, openai, deepseek, qwen, claude
所有 provider 使用 OpenAI 兼容协议
"""
from __future__ import annotations

import asyncio
import logging
import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from config import get_settings
from core import BaseLLM, Message


logger = logging.getLogger(__name__)

class OpenAICompatibleLLM(BaseLLM):
    """OpenAI 兼容协议 LLM 实现"""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> Message:
        """同步聊天（带重试）"""
        formatted = self._format_messages(messages)
        max_retries = kwargs.pop("max_retries", 3)
        retry_delay = kwargs.pop("retry_delay", 1.0)

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=formatted,
                    max_tokens=kwargs.get("max_tokens", self._max_tokens),
                    temperature=kwargs.get("temperature", self._temperature),
                    tools=kwargs.get("tools"),
                    tool_choice=kwargs.get("tool_choice", "auto"),
                )
                break
            except Exception as e:
                last_error = e
                logger.warning(f"LLM调用失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    raise RuntimeError(f"LLM调用失败（已重试{max_retries}次）: {last_error}") from last_error

        choice = response.choices[0]
        msg = choice.message

        return Message(
            role="assistant",
            content=msg.content or "",
            tool_calls=(
                [tc.model_dump() for tc in msg.tool_calls]
                if msg.tool_calls
                else None
            ),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式聊天（带重试）"""
        formatted = self._format_messages(messages)
        max_retries = kwargs.pop("max_retries", 2)
        retry_delay = kwargs.pop("retry_delay", 0.5)

        last_error = None
        for attempt in range(max_retries):
            try:
                stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=formatted,
                    max_tokens=kwargs.get("max_tokens", self._max_tokens),
                    temperature=kwargs.get("temperature", self._temperature),
                    stream=True,
                )
                break
            except Exception as e:
                last_error = e
                logger.warning(f"LLM流式调用失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    raise RuntimeError(f"LLM流式调用失败（已重试{max_retries}次）: {last_error}") from last_error

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """格式化为 OpenAI API 消息格式"""
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            formatted.append(entry)
        return formatted


# ============================================================
# Provider 配置映射
# ============================================================

_PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
    "mimo": {
        "api_base": "https://token-plan-cn.xiaomimimo.com/v1",
        "model": "mimo-v2.5-pro",
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "qwen": {
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "claude": {
        "api_base": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-20241022",
    },
}


def create_llm(provider: str | None = None) -> BaseLLM:
    """LLM 工厂函数 — 根据 provider 创建对应实例"""
    settings = get_settings()
    provider = provider or settings.MODEL_PROVIDER

    # 从配置获取 API Key 和 API Base
    llm_settings = settings.llm
    api_key = llm_settings.API_KEY
    api_base = llm_settings.API_BASE
    model = llm_settings.MODEL

    # 如果 API_BASE 是默认值且有预设配置，使用预设
    if provider in _PROVIDER_CONFIGS:
        cfg = _PROVIDER_CONFIGS[provider]
        if api_base == "https://api.openai.com/v1":
            api_base = cfg["api_base"]
        if not model or model == "gpt-4o":
            model = cfg["model"]

    return OpenAICompatibleLLM(
        api_key=api_key,
        api_base=api_base,
        model=model,
        max_tokens=llm_settings.MAX_TOKENS,
        temperature=llm_settings.TEMPERATURE,
    )
