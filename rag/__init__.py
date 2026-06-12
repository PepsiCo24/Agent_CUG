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

# Gov webpage noise markers (per-line check)
_GOV_NOISE_MARKERS = [
    re.compile(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{2}:\d{2}'),
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日\s+星期'),
    re.compile(r'请输入关键词'),
    re.compile(r'^\s*首\s*页\s+'),
    re.compile(r'^\s*首页\s*>'),
    re.compile(r'走进\S+'),
    re.compile(r'政府网站标识码'),
    re.compile(r'主办单位[：:]'),
    re.compile(r'鄂ICP备'),
    re.compile(r'鄂公网安备'),
    re.compile(r'^\s*索\s*引\s*号'),
    re.compile(r'政府信息公开'),
    re.compile(r'网上服务'),
    re.compile(r'互动交流'),
    re.compile(r'www\.\w+\.\w+'),
    re.compile(r'^\d+/\d+$'),
]

def _is_noise_chunk(content: str) -> bool:
    """Check if a chunk is webpage UI noise rather than document content.

    Uses line-level noise ratio: if >40% of non-empty lines match known
    gov noise patterns, the chunk is treated as noise.
    """
    stripped = content.strip()
    if len(stripped) < 20:
        return True
    lines = [l for l in stripped.split('\n') if l.strip()]
    if not lines:
        return True
    noise_lines = sum(
        1 for l in lines
        if any(m.search(l) for m in _GOV_NOISE_MARKERS)
    )
    noise_ratio = noise_lines / len(lines)
    # If >40% of lines are noise, filter it out
    if noise_ratio > 0.4:
        return True
    # Also check for breadcrumb-heavy chunks
    if ' > ' in stripped and len(stripped) < 100:
        return True
    # Pure navigation / breadcrumb
    if re.match(r'^[^\n]*首页\s*>', stripped) and len(stripped) < 80:
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
        """摄入单个文件

        Merges all pages into a single text before chunking so that the
        article-aware splitter can detect article boundaries that fall
        across page breaks (common in PDF government documents).
        """
        pages = load_document(file_path)
        if not pages:
            return 0

        path = Path(file_path)
        # Merge pages so article boundaries can be found across pages
        merged_text = "\n".join(pages)
        chunks = self._chunker.split_documents(
            [merged_text],
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

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document."""
        return await self._retriever.delete_by_doc_id(doc_id)

    async def query_with_doc_ids(
        self, query: str, doc_ids: list[str] | None = None, top_k: int | None = None
    ) -> list[Document]:
        """检索，可选按文档ID过滤"""
        k = top_k or self._top_k
        fetch_k = max(k * 4, 20)
        docs = await self._retriever.retrieve(query, top_k=fetch_k, doc_ids=doc_ids)
        if self._rerank_enabled and docs:
            docs = await self._reranker.rerank(query, docs)
        return docs[:k]

    @property
    def document_count(self) -> int:
        return self._retriever.count
