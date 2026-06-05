"""
RAG 检索器 — 基于 Chroma 的向量检索
"""
from __future__ import annotations

import uuid
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaConfig

from config import get_settings
from core import BaseRetriever, Document
from embedding import create_embedding


class ChromaRetriever(BaseRetriever):
    """Chroma 向量检索器"""

    def __init__(self) -> None:
        settings = get_settings()
        chroma_dir = settings.resolve_path(settings.chroma.PERSIST_DIR)
        chroma_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaConfig(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedding_fn = create_embedding()

    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> list[Document]:
        """检索相关文档"""
        if self._collection.count() == 0:
            return []

        query_emb = await self._embedding_fn.embed_single(query)

        results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents: list[Document] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0

                documents.append(Document(
                    id=doc_id,
                    content=content,
                    metadata=meta or {},
                    score=1.0 - min(distance, 1.0),  # cosine distance -> similarity
                ))

        return documents

    async def add_documents(self, documents: list[Document]) -> None:
        """批量添加文档"""
        if not documents:
            return

        texts = [d.content for d in documents]
        embeddings = await self._embedding_fn.embed(texts)

        ids = [d.id or str(uuid.uuid4()) for d in documents]
        metadatas = [d.metadata for d in documents]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    async def delete(self, doc_ids: list[str]) -> None:
        """删除文档"""
        if doc_ids:
            self._collection.delete(ids=doc_ids)

    @property
    def count(self) -> int:
        return self._collection.count()
