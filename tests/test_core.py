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
        assert len(definitions) == 2

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
