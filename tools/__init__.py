"""
Tool Framework — 统一工具接口 + 内置工具实现
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from core import BaseTool, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


# ============================================================
# Time Tool
# ============================================================

class TimeTool(BaseTool):
    """获取当前时间"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_current_time",
            description="获取当前日期和时间，支持指定时区",
            parameters={
                "type": "object",
                "properties": {
                    "timezone_offset": {
                        "type": "string",
                        "description": "时区偏移量，如 '+08:00'，默认为 UTC",
                    }
                },
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        now = datetime.now(timezone.utc)
        formatted = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        return ToolResult(
            success=True,
            output=f"当前时间: {formatted}",
            metadata={"timestamp": now.isoformat()},
        )


# ============================================================
# Calculator Tool
# ============================================================

class CalculatorTool(BaseTool):
    """安全计算器"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculate",
            description="执行数学计算。支持基本运算：+, -, *, /, **, %, // 以及 abs, round, min, max, sum, pow, int, float",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4' 或 'round(3.14159, 2)' 或 'pow(2, 10)'",
                    }
                },
                "required": ["expression"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        expression = kwargs.get("expression", "")
        if not expression:
            return ToolResult(success=False, output="", error="表达式不能为空")

        allowed_names: dict[str, Any] = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "int": int, "float": float, "pow": pow,
            "len": len, "divmod": divmod, "complex": complex,
        }

        try:
            code = compile(expression.strip(), "<calculator>", "eval")
            result = eval(code, {"__builtins__": {}}, allowed_names)
            return ToolResult(
                success=True,
                output=f"{expression} = {result}",
                metadata={"expression": expression, "result": str(result)},
            )
        except SyntaxError as e:
            return ToolResult(
                success=False, output="",
                error=f"表达式语法错误: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="",
                error=f"计算错误: {e}",
            )


# ============================================================
# RAG Tool
# ============================================================

class RAGTool(BaseTool):
    """知识库检索工具"""

    def __init__(self) -> None:
        self._pipeline = None

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_knowledge_base",
            description="从本地知识库中检索相关文档内容。用于查找已上传文档中的信息。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询文本",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from rag import RAGPipeline

            if self._pipeline is None:
                self._pipeline = RAGPipeline()

            query = kwargs.get("query", "")
            top_k = kwargs.get("top_k", 5)

            if not query.strip():
                return ToolResult(success=False, output="", error="查询文本不能为空")

            docs = await self._pipeline.query(query, top_k=top_k)

            if not docs:
                return ToolResult(
                    success=True,
                    output="知识库中未找到相关文档。",
                    metadata={"count": 0},
                )

            parts: list[str] = []
            for i, doc in enumerate(docs):
                source = doc.metadata.get("source", "未知来源")
                parts.append(
                    f"[来源 {i+1}: {source}] (相似度: {doc.score:.2%})\n{doc.content[:500]}"
                )

            output = "\n\n---\n\n".join(parts)
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "count": len(docs),
                    "sources": [
                        {"source": d.metadata.get("source", "未知"), "score": round(d.score, 4)}
                        for d in docs
                    ],
                },
            )
        except Exception as e:
            logger.error(f"RAG Tool 执行失败: {e}")
            return ToolResult(
                success=False, output="", error=f"知识库检索失败: {e}",
            )


# ============================================================
# Search Tool (Web Search via DuckDuckGo)
# ============================================================

class SearchTool(BaseTool):
    """网络搜索工具（基于 DuckDuckGo）"""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="通过网络搜索获取最新信息。用于查找实时数据、新闻、事实等。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数，默认 3",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 3)

        if not query.strip():
            return ToolResult(success=False, output="", error="搜索关键词不能为空")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # 使用 DuckDuckGo Instant Answer API
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                )

                if resp.status_code != 200:
                    return ToolResult(
                        success=False, output="",
                        error=f"搜索请求失败: HTTP {resp.status_code}",
                    )

                data = resp.json()

                parts: list[str] = []

                # Abstract
                abstract = data.get("AbstractText", "")
                if abstract:
                    parts.append(f"摘要: {abstract}")

                # Related topics
                related = data.get("RelatedTopics", [])
                for i, topic in enumerate(related[:max_results]):
                    if isinstance(topic, dict) and topic.get("Text"):
                        parts.append(f"结果 {i + 1}: {topic['Text']}")

                if not parts:
                    return ToolResult(
                        success=True,
                        output=f"未找到关于「{query}」的相关搜索结果。",
                        metadata={"query": query, "results": 0},
                    )

                output = "\n\n".join(parts)
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={
                        "query": query,
                        "results": len(parts),
                        "source": "DuckDuckGo",
                    },
                )

        except httpx.TimeoutException:
            return ToolResult(
                success=False, output="",
                error=f"搜索超时（{self._timeout}秒）",
            )
        except Exception as e:
            logger.error(f"Search Tool 执行失败: {e}")
            return ToolResult(
                success=False, output="", error=f"搜索失败: {e}",
            )


# ============================================================
# Tool Registry
# ============================================================

class ToolRegistry:
    """工具注册中心"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._usage_count: dict[str, int] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_definitions(self) -> list[dict[str, Any]]:
        """获取所有工具定义（OpenAI function calling 格式）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.definition.name,
                    "description": t.definition.description,
                    "parameters": t.definition.parameters,
                },
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False, output="", error=f"未知工具: {name}"
            )
        try:
            result = await tool.execute(**kwargs)
            self._usage_count[name] = self._usage_count.get(name, 0) + 1
            return result
        except Exception as e:
            logger.error(f"工具 [{name}] 执行异常: {e}")
            return ToolResult(
                success=False, output="", error=f"工具执行异常: {e}",
            )

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def count(self) -> int:
        return len(self._tools)

    def get_usage_stats(self) -> dict[str, int]:
        """获取工具使用统计"""
        return dict(self._usage_count)


# ============================================================
# 默认注册
# ============================================================

def create_tool_registry() -> ToolRegistry:
    """创建并注册所有默认工具"""
    registry = ToolRegistry()
    registry.register(TimeTool())
    registry.register(CalculatorTool())
    registry.register(RAGTool())
    registry.register(SearchTool())
    return registry
