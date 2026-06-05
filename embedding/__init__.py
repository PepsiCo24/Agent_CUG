"""
Embedding Adapter — 统一 Embedding 接口实现
支持: siliconflow, openai
"""
from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from config import get_settings
from core import BaseEmbedding


class OpenAICompatibleEmbedding(BaseEmbedding):
    """OpenAI 兼容协议 Embedding 实现"""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model = model
        self._dimension: int | None = None

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # bge-m3 默认 1024 维
            if "bge-m3" in self._model.lower():
                return 1024
            return 1536  # OpenAI 默认
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化"""
        if not texts:
            return []

        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )

        embeddings = [d.embedding for d in response.data]
        if embeddings and self._dimension is None:
            self._dimension = len(embeddings[0])

        return embeddings

    async def embed_single(self, text: str) -> list[float]:
        """单文本向量化"""
        results = await self.embed([text])
        return results[0]


_PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
    "siliconflow": {
        "api_base": "https://api.siliconflow.cn/v1",
        "model": "BAAI/bge-m3",
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model": "text-embedding-3-small",
    },
}


def create_embedding(provider: str | None = None) -> BaseEmbedding:
    """Embedding 工厂函数"""
    settings = get_settings()
    provider = provider or settings.EMBEDDING_PROVIDER

    emb_settings = settings.embedding
    api_key = emb_settings.API_KEY
    api_base = emb_settings.API_BASE
    model = emb_settings.MODEL

    if provider in _PROVIDER_CONFIGS:
        cfg = _PROVIDER_CONFIGS[provider]
        if api_base == "https://api.openai.com/v1":
            api_base = cfg["api_base"]
        if not model or model == "text-embedding-3-small":
            model = cfg["model"]

    return OpenAICompatibleEmbedding(
        api_key=api_key,
        api_base=api_base,
        model=model,
    )
