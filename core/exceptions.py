"""
统一异常处理 — Agent_CUG 自定义异常体系
"""
from __future__ import annotations


class AgentCUGError(Exception):
    """Agent_CUG 基础异常"""
    def __init__(self, message: str, code: str = "AGENT_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class ConfigurationError(AgentCUGError):
    """配置错误"""
    def __init__(self, message: str) -> None:
        super().__init__(message, code="CONFIG_ERROR")


class LLMError(AgentCUGError):
    """LLM 调用错误"""
    def __init__(self, message: str, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}", code="LLM_ERROR")


class EmbeddingError(AgentCUGError):
    """Embedding 错误"""
    def __init__(self, message: str, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}", code="EMBEDDING_ERROR")


class RAGError(AgentCUGError):
    """RAG 错误"""
    def __init__(self, message: str) -> None:
        super().__init__(message, code="RAG_ERROR")


class MemoryError(AgentCUGError):
    """Memory 错误"""
    def __init__(self, message: str) -> None:
        super().__init__(message, code="MEMORY_ERROR")


class ToolError(AgentCUGError):
    """Tool 错误"""
    def __init__(self, message: str, tool_name: str = "unknown") -> None:
        self.tool_name = tool_name
        super().__init__(f"[{tool_name}] {message}", code="TOOL_ERROR")


class AgentWorkflowError(AgentCUGError):
    """Agent 工作流错误"""
    def __init__(self, message: str, node: str = "unknown") -> None:
        self.node = node
        super().__init__(f"[{node}] {message}", code="WORKFLOW_ERROR")


class ValidationError(AgentCUGError):
    """输入验证错误"""
    def __init__(self, message: str, field: str = "unknown") -> None:
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")