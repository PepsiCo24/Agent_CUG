"""
核心抽象层 — 定义 Agent 系统的所有统一接口
遵循 SOLID 原则：依赖抽象而非具体实现
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Protocol

from pydantic import BaseModel, Field


# ============================================================
# 消息模型
# ============================================================

class Message(BaseModel):
    """统一消息模型"""
    role: str  # system / user / assistant / tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """聊天请求"""
    user_input: str
    conversation_id: str | None = None
    files: list[str] | None = None  # 上传文件路径列表


class ChatResponse(BaseModel):
    """聊天响应"""
    conversation_id: str
    answer: str
    sources: list[dict[str, str]] = Field(default_factory=list)  # RAG 来源
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


# ============================================================
# LLM 抽象
# ============================================================

class BaseLLM(ABC):
    """LLM 统一接口"""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> Message:
        """同步聊天"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式聊天"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


# ============================================================
# Embedding 抽象
# ============================================================

@dataclass
class EmbeddingResult:
    """嵌入结果"""
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseEmbedding(ABC):
    """Embedding 统一接口"""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化"""
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """单文本向量化"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


# ============================================================
# Memory 抽象
# ============================================================

@dataclass
class MemoryItem:
    """记忆条目"""
    id: str
    content: str
    role: str
    embedding: list[float] | None = None
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    ttl: int | None = None  # 存活天数
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseMemory(ABC):
    """Memory 统一接口"""

    @abstractmethod
    async def add(self, item: MemoryItem) -> str:
        """添加记忆"""
        ...

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> list[MemoryItem]:
        """检索相关记忆"""
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 20) -> list[MemoryItem]:
        """获取最近记忆"""
        ...

    @abstractmethod
    async def score(self, item_id: str, importance: float) -> None:
        """评分"""
        ...

    @abstractmethod
    async def deduplicate(self, threshold: float = 0.95) -> int:
        """去重，返回删除数量"""
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """清理过期记忆"""
        ...


# ============================================================
# Tool 抽象
# ============================================================

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolDefinition(BaseModel):
    """工具定义（用于传递给 LLM）"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class BaseTool(ABC):
    """Tool 统一接口"""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """工具定义"""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具"""
        ...


# ============================================================
# Retriever 抽象
# ============================================================

@dataclass
class Document:
    """文档"""
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    score: float = 0.0


class BaseRetriever(ABC):
    """检索器统一接口"""

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> list[Document]:
        ...

    @abstractmethod
    async def add_documents(self, documents: list[Document]) -> None:
        ...

    @abstractmethod
    async def delete(self, doc_ids: list[str]) -> None:
        ...


# ============================================================
# Reranker 抽象
# ============================================================

class BaseReranker(ABC):
    """重排序器统一接口"""

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[Document]
    ) -> list[Document]:
        ...
