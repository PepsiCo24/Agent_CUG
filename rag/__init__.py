"""
RAG Pipeline — 完整的 RAG 流程编排
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import re
from config import get_settings
from core import Document
from rag.chunker import TextChunker
from rag.loaders import load_document
from rag.retriever import ChromaRetriever
from rag.reranker import KeywordReranker

# Patterns to identify webpage UI / navigation noise chunks
_NOISE_CHUNK_PATTERNS = [
    re.compile(r'^\s*(?:首\s*页|Home)\s*$', re.IGNORECASE),
    re.compile(r'^\s*请输入关键词搜索\s*$'),
    re.compile(r'^\s*关闭\s*$'),
    re.compile(r'^\s*[一-鿿]+政府网\s*$'),
    re.compile(r'^\s*索\s*引\s*号\s*[:]\s*\d'),
    re.compile(r'^\s*走进[一-鿿]+\s*$'),
]

def _is_noise_chunk(content: str) -> bool:
    """Check if a chunk is webpage UI noise rather than document content."""
    # Very short chunks that are pure UI
    stripped = content.strip()
    if len(stripped) < 20:
        return True
    # Match known noise patterns
    for pat in _NOISE_CHUNK_PATTERNS:
        if pat.search(stripped):
            return True
    # Chunks that are mostly URLs and navigation
    if ' > ' in stripped and len(stripped) < 100:
        return True
    return False


class RAGPipeline:
    """
    RAG 流水线：
    Document Loader → Chunking → Embedding → Chroma → Retriever → Reranker
    """
    _instance: "RAGPipeline | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        settings = get_settings()
        self._chunker = TextChunker(
            chunk_size=settings.rag.CHUNK_SIZE,
            chunk_overlap=settings.rag.CHUNK_OVERLAP,
            article_aware=True,
        )
        self._retriever = ChromaRetriever()
        self._reranker = KeywordReranker()
        self._rerank_enabled = settings.rag.RERANK_ENABLED
        self._initialized = True
        self._top_k = settings.rag.TOP_K

    async def ingest_file(
        self, file_path: str | Path, metadata: dict[str, Any] | None = None
    ) -> int:
        """摄入单个文件"""
        pages = load_document(file_path)
        if not pages:
            return 0

        path = Path(file_path)
        chunks = self._chunker.split_documents(
            pages,
            metadata={
                "source": path.name,
                "file_path": str(path.absolute()),
                **(metadata or {}),
            },
        )

        documents = [
            Document(
                id=str(uuid.uuid4()),
                content=chunk["content"],
                metadata=chunk["metadata"],
            )
            for chunk in chunks
            if not _is_noise_chunk(chunk["content"])
        ]

        await self._retriever.add_documents(documents)
        return len(documents)

    async def ingest_text(
        self, text: str, metadata: dict[str, Any] | None = None
    ) -> int:
        """摄入纯文本"""
        chunks = self._chunker.split_documents(
            [text], metadata=metadata
        )

        documents = [
            Document(
                id=str(uuid.uuid4()),
                content=chunk["content"],
                metadata=chunk["metadata"],
            )
            for chunk in chunks
            if not _is_noise_chunk(chunk["content"])
        ]

        await self._retriever.add_documents(documents)
        return len(documents)

    async def query(
        self, query: str, top_k: int | None = None
    ) -> list[Document]:
        """检索相关文档"""
        k = top_k or self._top_k
                # Fetch more candidates for better reranking coverage
        fetch_k = max(k * 4, 20)
        docs = await self._retriever.retrieve(query, top_k=fetch_k)

        if self._rerank_enabled and docs:
            docs = await self._reranker.rerank(query, docs)

        # Return top_k after reranking
        return docs[:k]

    async def query_with_context(
        self, query: str, top_k: int | None = None
    ) -> tuple[str, list[Document]]:
        """检索并构建上下文文本"""
        docs = await self.query(query, top_k=top_k)

        if not docs:
            return "", []

        context_parts: list[str] = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知")
            context_parts.append(
                f"[文档 {i+1}] (来源: {source})\n{doc.content}"
            )

        context = "\n\n---\n\n".join(context_parts)
        return context, docs

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None

    @property
    def document_count(self) -> int:
        return self._retriever.count
