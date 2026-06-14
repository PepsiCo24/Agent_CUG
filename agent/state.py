"""
Agent 状态定义 — LangGraph State
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from core import Document, MemoryItem


class AgentState(TypedDict):
    """Agent 工作流状态"""
    # 输入
    user_input: str
    conversation_id: str | None
    doc_ids: list[str] | None
    mode: str  # "chat" | "rag" | "tool" | "orchestrate"

    # 对话历史（使用 LangGraph 的 add_messages reducer）
    chat_history: Annotated[list[Any], add_messages]

    # 检索结果
    retrieved_docs: list[Document]
    retrieved_memory: list[MemoryItem]

    # 工具调用
    tool_calls: list[dict[str, Any]]
    observations: list[str]

    # 中间产物
    rag_context: str
    memory_context: str

    # 最终输出
    final_answer: str

    # 路由
    next_action: str  # "rag" | "tool" | "llm" | "end"
    iteration: int
