"""
集成测试：API 端点 + Agent 工作流
"""
from __future__ import annotations

import pytest
# httpx via conftest

# app imported via conftest
from tools import create_tool_registry, TimeTool, CalculatorTool, RAGTool, SearchTool


# ============================================================
# API 集成测试
# ============================================================




class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert "document_count" in data

    @pytest.mark.asyncio
    async def test_config(self, async_client: AsyncClient):
        resp = await async_client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_provider" in data
        assert "llm_model" in data
        assert "embedding_model" in data
        assert "rag_enabled" in data

    @pytest.mark.asyncio
    async def test_history(self, async_client: AsyncClient):
        resp = await async_client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversations" in data


class TestRAGAPI:
    @pytest.mark.asyncio
    async def test_rag_query_empty(self, async_client: AsyncClient):
        resp = await async_client.post("/api/rag/query", json={"query": "", "top_k": 3})
        # 空查询也可以，返回空结果
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data

    @pytest.mark.asyncio
    async def test_rag_upload_no_file(self, async_client: AsyncClient):
        resp = await async_client.post("/api/rag/upload")
        assert resp.status_code == 422  # FastAPI 参数验证


class TestChatAPI:
    @pytest.mark.asyncio
    async def test_chat_empty_message(self, async_client: AsyncClient):
        resp = await async_client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422  # message 为空时验证失败

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_exists(self, async_client: AsyncClient):
        # 测试流式端点存在且返回正确 Content-Type
        resp = await async_client.post(
            "/api/chat/stream",
            json={"message": "hello"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


# ============================================================
# Tool 集成测试
# ============================================================

class TestToolIntegration:
    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        registry = create_tool_registry()
        expected = {"get_current_time", "calculate", "search_knowledge_base", "web_search"}
        assert set(registry.tool_names) == expected
        assert registry.count == 4

    @pytest.mark.asyncio
    async def test_time_tool_execution(self):
        tool = TimeTool()
        result = await tool.execute()
        assert result.success
        assert "当前时间" in result.output
        assert "timestamp" in result.metadata

    @pytest.mark.asyncio
    async def test_calculator_complex(self):
        tool = CalculatorTool()
        test_cases = [
            ("2 ** 10", True),
            ("round(3.14159, 2)", True),
            ("min(5, 3, 9, 1)", True),
            ("sum([1, 2, 3, 4, 5])", True),
            ("__import__('os').system('dir')", False),  # 安全检查
        ]
        for expr, should_succeed in test_cases:
            result = await tool.execute(expression=expr)
            assert result.success == should_succeed, f"Expression: {expr}"

    @pytest.mark.asyncio
    async def test_search_tool_empty_query(self):
        tool = SearchTool()
        result = await tool.execute(query="")
        assert not result.success
        assert "不能为空" in result.error

    @pytest.mark.asyncio
    async def test_rag_tool_empty_query(self):
        tool = RAGTool()
        result = await tool.execute(query="")
        assert not result.success
        assert "不能为空" in result.error

    @pytest.mark.asyncio
    async def test_registry_execute_all(self):
        registry = create_tool_registry()

        # Time
        r = await registry.execute("get_current_time")
        assert r.success

        # Calculator
        r = await registry.execute("calculate", expression="100 + 200")
        assert r.success
        assert "300" in r.output

        # Unknown tool
        r = await registry.execute("nonexistent_tool")
        assert not r.success
        assert "未知工具" in r.error

    @pytest.mark.asyncio
    async def test_tool_definitions_format(self):
        registry = create_tool_registry()
        defs = registry.get_definitions()
        assert len(defs) == 4

        for d in defs:
            assert d["type"] == "function"
            assert "name" in d["function"]
            assert "description" in d["function"]
            assert "parameters" in d["function"]
            assert d["function"]["parameters"]["type"] == "object"


# ============================================================
# Agent Workflow 集成测试
# ============================================================

class TestAgentWorkflow:
    @pytest.mark.asyncio
    async def test_agent_state_creation(self):
        from agent.state import AgentState

        state: AgentState = {
            "user_input": "test",
            "conversation_id": None,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
        }
        assert state["user_input"] == "test"
        assert state["next_action"] == "chat"

    @pytest.mark.asyncio
    async def test_agent_router_rag(self):
        from agent import AgentWorkflow

        agent = AgentWorkflow()
        state: dict = {
            "user_input": "查询文档中的内容",
            "conversation_id": None,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
        }
        result = await agent._router(state)
        assert result["next_action"] == "rag"

    @pytest.mark.asyncio
    async def test_agent_router_tool(self):
        from agent import AgentWorkflow

        agent = AgentWorkflow()
        state: dict = {
            "user_input": "计算 100 * 50",
            "conversation_id": None,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
        }
        result = await agent._router(state)
        assert result["next_action"] == "tool"

    @pytest.mark.asyncio
    async def test_agent_router_chat(self):
        from agent import AgentWorkflow

        agent = AgentWorkflow()
        state: dict = {
            "user_input": "你好，今天天气怎么样？",
            "conversation_id": None,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
        }
        result = await agent._router(state)
        assert result["next_action"] == "chat"

    @pytest.mark.asyncio
    async def test_agent_tool_planning(self):
        from agent import AgentWorkflow

        agent = AgentWorkflow()
        state: dict = {
            "user_input": "计算 1+2+3",
            "conversation_id": None,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "tool",
            "iteration": 0,
        }
        result = await agent._tool_planning(state)
        assert len(result["tool_calls"]) >= 1
        assert result["tool_calls"][0]["name"] == "calculate"


# ============================================================
# Prompt 测试
# ============================================================

class TestPrompts:
    def test_system_prompt_exists(self):
        from prompt import SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE

        assert len(SYSTEM_PROMPT) > 0
        assert "Agent_CUG" in SYSTEM_PROMPT
        assert "{context}" in RAG_PROMPT_TEMPLATE
        assert "{question}" in RAG_PROMPT_TEMPLATE
        assert "{history}" in RAG_PROMPT_TEMPLATE


# ============================================================
# LLM 配置测试
# ============================================================

class TestLLMConfig:
    def test_llm_factory(self):
        from llm import create_llm, _PROVIDER_CONFIGS

        assert "mimo" in _PROVIDER_CONFIGS
        assert "openai" in _PROVIDER_CONFIGS
        assert "deepseek" in _PROVIDER_CONFIGS
        assert "qwen" in _PROVIDER_CONFIGS
        assert "claude" in _PROVIDER_CONFIGS

        llm = create_llm("mimo")
        assert llm.model_name is not None


class TestEmbeddingConfig:
    def test_embedding_factory(self):
        from embedding import create_embedding

        emb = create_embedding("siliconflow")
        assert emb.dimension > 0



