"""
核心模块单元测试
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from config import get_settings
from core.base import Message, ChatRequest, ChatResponse, ToolResult, Document, MemoryItem
from tools import CalculatorTool, TimeTool, ToolRegistry, create_tool_registry
from rag.chunker import TextChunker
from rag.loaders import TextLoader, MarkdownLoader


class TestConfig:
    def test_settings_load(self):
        settings = get_settings()
        assert settings.PROJECT_NAME == "Agent_CUG"
        assert settings.MODEL_PROVIDER in ("mimo", "openai", "deepseek", "qwen", "claude")
        assert settings.DOMAIN_NAME == "localhost"
        assert settings.llm is not None
        assert settings.embedding is not None

    def test_resolve_path(self):
        settings = get_settings()
        path = settings.resolve_path("./data/test.db")
        assert path.is_absolute()
        assert "data" in str(path)


class TestCoreModels:
    def test_message_creation(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None

    def test_chat_request(self):
        req = ChatRequest(user_input="Hi", conversation_id="abc")
        assert req.user_input == "Hi"
        assert req.conversation_id == "abc"

    def test_document_model(self):
        doc = Document(id="1", content="test", metadata={"source": "test.txt"})
        assert doc.id == "1"
        assert doc.metadata["source"] == "test.txt"


class TestTools:
    @pytest.mark.asyncio
    async def test_calculator_valid(self):
        tool = CalculatorTool()
        result = await tool.execute(expression="2 + 3 * 4")
        assert result.success
        assert "14" in result.output

    @pytest.mark.asyncio
    async def test_calculator_invalid(self):
        tool = CalculatorTool()
        result = await tool.execute(expression="__import__('os')")
        assert not result.success

    @pytest.mark.asyncio
    async def test_time_tool(self):
        tool = TimeTool()
        result = await tool.execute()
        assert result.success
        assert "当前时间" in result.output

    @pytest.mark.asyncio
    async def test_tool_registry(self):
        registry = create_tool_registry()
        assert "calculate" in registry.tool_names
        assert "get_current_time" in registry.tool_names

        definitions = registry.get_definitions()
        assert len(definitions) >= 2

    @pytest.mark.asyncio
    async def test_registry_execute(self):
        registry = create_tool_registry()
        result = await registry.execute("calculate", expression="1+1")
        assert result.success

        result = await registry.execute("unknown_tool")
        assert not result.success


class TestChunker:
    def test_basic_split(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Hello " * 50
        chunks = chunker.split(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_short_text(self):
        chunker = TextChunker(chunk_size=500)
        text = "Short text"
        chunks = chunker.split(text)
        assert len(chunks) == 1

    def test_split_documents(self):
        chunker = TextChunker(chunk_size=100)
        docs = ["Hello world " * 20, "Another doc " * 10]
        result = chunker.split_documents(docs, metadata={"source": "test"})
        assert len(result) > 0
        for r in result:
            assert "content" in r
            assert r["metadata"]["source"] == "test"




class TestMemorySingleton:
    """测试 MemoryManager 全局单例模式"""
    @pytest.mark.asyncio
    async def test_memory_singleton(self):
        """验证 MemoryManager 共享 Chroma 客户端"""
        from memory import MemoryManager
        m1 = MemoryManager()
        m2 = MemoryManager()
        await m1._ensure_chroma()
        await m2._ensure_chroma()
        # After initialization, both should share same chroma collection
        assert m1._chroma_ready
        assert m2._chroma_ready
        assert m1._chroma_client is m2._chroma_client

    @pytest.mark.asyncio
    async def test_memory_add_and_retrieve(self):
        """验证记忆添加和检索"""
        from memory import MemoryManager
        m = MemoryManager()
        item = MemoryItem(id="", content="test memory content", role="user")
        mid = await m.add(item)
        assert mid

        results = await m.get_recent(limit=5)
        assert len(results) > 0


class TestRAGSingleton:
    """测试 RAGPipeline 单例"""
    def test_rag_singleton(self):
        from rag import RAGPipeline
        p1 = RAGPipeline()
        p2 = RAGPipeline()
        assert p1 is p2


class TestLoaders:
    def test_text_loader(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        loader = TextLoader()
        result = loader.load(str(f))
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_markdown_loader(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Title\nContent", encoding="utf-8")
        loader = MarkdownLoader()
        result = loader.load(str(f))
        assert len(result) == 1
        assert "# Title" in result[0]



class TestLLMRetry:
    """测试 LLM 重试逻辑"""
    @pytest.mark.asyncio
    async def test_llm_retry_on_failure(self):
        from unittest.mock import AsyncMock, patch
        from llm import OpenAICompatibleLLM
        llm = OpenAICompatibleLLM(api_key="test", api_base="http://test", model="test")
        llm._client = AsyncMock()
        llm._client.chat.completions.create = AsyncMock()

        # 前两次失败，第三次成功
        from openai.types.chat import ChatCompletion, ChatCompletionMessage
        from openai.types.chat.chat_completion import Choice

        mock_msg = AsyncMock()
        mock_msg.content = "success"
        mock_msg.tool_calls = None

        mock_choice = AsyncMock()
        mock_choice.message = mock_msg

        mock_resp = AsyncMock()
        mock_resp.choices = [mock_choice]

        llm._client.chat.completions.create.side_effect = [
            Exception("fail1"),
            Exception("fail2"),
            mock_resp,
        ]
        from core import Message
        result = await llm.chat([Message(role="user", content="test")])
        assert result.content == "success"
        assert llm._client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_llm_retry_exhausted(self):
        from unittest.mock import AsyncMock
        from llm import OpenAICompatibleLLM
        llm = OpenAICompatibleLLM(api_key="test", api_base="http://test", model="test")
        llm._client = AsyncMock()
        llm._client.chat.completions.create = AsyncMock(side_effect=Exception("always fails"))
        from core import Message
        with pytest.raises(RuntimeError, match="LLM调用失败"):
            await llm.chat([Message(role="user", content="test")])
