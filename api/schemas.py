"""
API Schemas — Pydantic V2 请求/响应模型
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=32000, description="用户消息")
    conversation_id: str | None = Field(None, description="会话 ID")


class ChatResponse(BaseModel):
    """聊天响应"""
    conversation_id: str = Field(..., description="会话 ID")
    answer: str = Field(..., description="AI 回答")
    sources: list[dict[str, str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class RAGQueryRequest(BaseModel):
    """RAG 查询请求"""
    query: str = Field(..., description="查询文本")
    top_k: int = Field(5, ge=1, le=20)


class RAGQueryResponse(BaseModel):
    """RAG 查询响应"""
    documents: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    filename: str = Field(..., description="文件名")
    chunks: int = Field(0, description="分块数量")
    status: str = Field("ok")


class HealthResponse(BaseModel):
    """健康检查"""
    status: str = "ok"
    version: str = "1.0.0"
    document_count: int = 0


class HistoryItem(BaseModel):
    """历史记录条目"""
    id: str
    title: str
    created_at: str
    message_count: int = 0


class HistoryResponse(BaseModel):
    """历史记录响应"""
    conversations: list[HistoryItem] = Field(default_factory=list)
