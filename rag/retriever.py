"""
RAG 检索器 — 基于 Chroma 的向量检索
"""
from __future__ import annotations

import uuid
from typing import Any

import chromadb

from config import get_settings
from core import BaseRetriever, Document
from embedding import create_embedding


# ?????ChromaDB ??????
_global_client: chromadb.PersistentClient | None = None
_global_collection: chromadb.Collection | None = None


def _get_chroma_collection() -> chromadb.Collection:
    """??????? ChromaDB ????????"""
    global _global_client, _global_collection
    if _global_collection is None:
        settings = get_settings()
        chroma_dir = settings.resolve_path(settings.chroma.PERSIST_DIR)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        _global_client = chromadb.PersistentClient(path=str(chroma_dir))
        _global_collection = _global_client.get_or_create_collection(
            name=settings.chroma.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _global_collection


class ChromaRetriever(BaseRetriever):
    """Chroma ?????"""


    async def _retry_operation(self, operation, max_retries=3, *args, **kwargs):
        """带重试的操作包装"""
        import asyncio
        last_error = None
        for attempt in range(max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        raise last_error

    def __init__(self) -> None:
        self._collection = _get_chroma_collection()
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
    async def clear_all(self) -> int:
        """清除所有文档"""
        try:
            count = self._collection.count()
            if count > 0:
                ids = self._collection.get()["ids"]
                self._collection.delete(ids=ids)
            return count
        except Exception:
            return 0


    @property
    def count(self) -> int:
        return self._collection.count()
