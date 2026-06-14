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

# New tools for Agent_CUG
import httpx
import logging
import subprocess
import shlex
from typing import Any
from core import BaseTool, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)

class WeatherTool(BaseTool):
    """天气查询工具 - Open-Meteo API"""

    def __init__(self) -> None:
        self._timeout = 10.0

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_weather",
            description="查询指定城市的当前天气和预报信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "days": {"type": "integer", "description": "预报天数，默认1，最大3", "default": 1},
                },
                "required": ["city"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        city = kwargs.get("city", "").strip()
        days = min(kwargs.get("days", 1), 3)
        if not city:
            return ToolResult(success=False, output="", error="城市名称不能为空")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                geo_resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "zh"},
                )
                if geo_resp.status_code != 200 or not geo_resp.json().get("results"):
                    return ToolResult(success=False, output="", error=f"未找到城市: {city}")

                geo_data = geo_resp.json()["results"][0]
                lat, lon = geo_data["latitude"], geo_data["longitude"]
                display_name = geo_data.get("name", city)

                weather_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current_weather": "true",
                        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
                        "forecast_days": days, "timezone": "auto",
                    },
                )
                if weather_resp.status_code != 200:
                    return ToolResult(success=False, output="", error="天气查询失败")

                wdata = weather_resp.json()
                current = wdata.get("current_weather", {})
                daily = wdata.get("daily", {})

                wcodes = {0: "晴", 1: "大部晴", 2: "多云", 3: "阴", 45: "雾", 51: "小雨", 53: "中雨", 55: "大雨", 61: "小雨", 63: "中雨", 65: "暴雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 95: "雷暴"}

                parts = [f"地点: {display_name}"]
                wc = current.get("weathercode", 0)
                parts.append(f"当前温度: {current.get('temperature', 'N/A')} C | {wcodes.get(wc, '未知')} | 风速: {current.get('windspeed', 'N/A')} km/h")

                dates = daily.get("time", [])
                tmax = daily.get("temperature_2m_max", [])
                tmin = daily.get("temperature_2m_min", [])
                wcd = daily.get("weathercode", [])

                if dates:
                    parts.append("预报:")
                    for i in range(min(len(dates), days)):
                        parts.append(f"  {dates[i]}: {wcodes.get(wcd[i], 'N/A')} | {tmin[i]}~{tmax[i]} C")

                return ToolResult(success=True, output="\n".join(parts), metadata={"city": display_name})

        except httpx.TimeoutException:
            return ToolResult(success=False, output="", error="天气查询超时")
        except Exception as e:
            logger.error(f"WeatherTool error: {e}")
            return ToolResult(success=False, output="", error=f"天气查询失败: {e}")


class CommandExecutionTool(BaseTool):
    """安全的命令执行工具"""

    _ALLOWED = {"echo", "date", "time", "whoami", "hostname", "pwd", "ls", "dir", "cat", "head", "tail", "wc", "sort", "find", "grep", "python", "python3", "node", "npm", "pip", "git", "curl", "wget"}

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="execute_command",
            description="执行安全的系统命令。允许: echo, ls, cat, python, node, curl 等。",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string", "description": "要执行的命令"}},
                "required": ["command"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "").strip()
        if not command:
            return ToolResult(success=False, output="", error="命令不能为空")

        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        if not parts:
            return ToolResult(success=False, output="", error="无效的命令")

        base_cmd = parts[0].lower()
        if base_cmd not in self._ALLOWED:
            return ToolResult(success=False, output="", error=f"不允许的命令: {base_cmd}")

        dangerous = ["rm", "del", "format", "mkfs", "dd", "shutdown", "reboot"]
        cmd_lower = command.lower()
        for d in dangerous:
            if d in cmd_lower:
                return ToolResult(success=False, output="", error=f"禁止危险操作: {d}")

        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15, cwd=".")
            output = proc.stdout.strip()
            if proc.stderr:
                output += "\n[stderr]\n" + proc.stderr.strip()
            if not output:
                output = "(执行成功，无输出)"
            return ToolResult(success=True, output=output[:2000], metadata={"command": command, "exit_code": proc.returncode})
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="命令执行超时(15秒)")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"命令执行失败: {e}")


class IGSearchTool(BaseTool):
    """增强互联网搜索 - Wikipedia + DuckDuckGo"""

    def __init__(self) -> None:
        self._timeout = 15.0

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ig_search",
            description="增强互联网搜索，整合Wikipedia和DuckDuckGo结果",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最大结果数，默认5", "default": 5},
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        max_results = min(kwargs.get("max_results", 5), 10)
        if not query:
            return ToolResult(success=False, output="", error="搜索关键词不能为空")

        results: list[str] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Wikipedia
            try:
                resp = await client.get(
                    "https://zh.wikipedia.org/w/api.php",
                    params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": min(max_results, 5)},
                )
                if resp.status_code == 200:
                    sr = resp.json().get("query", {}).get("search", [])
                    if sr:
                        results.append("Wikipedia:")
                        for i, r in enumerate(sr[:max_results]):
                            snippet = r.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")[:300]
                            results.append(f"{i+1}. {r['title']}: {snippet}")
            except Exception:
                pass

            # DuckDuckGo
            try:
                resp = await client.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_html": "1"})
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        results.append("DuckDuckGo: " + abstract[:500])
            except Exception:
                pass

        if not results:
            return ToolResult(success=True, output=f"未找到关于 [{query}] 的搜索结果", metadata={"query": query, "results": 0})

        return ToolResult(success=True, output="\n\n".join(results), metadata={"query": query, "results": len(results)})


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
    registry.register(WeatherTool())
    registry.register(CommandExecutionTool())
    registry.register(IGSearchTool())
    registry.register(SearchTool())
    return registry
