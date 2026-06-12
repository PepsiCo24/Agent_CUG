"""
RAG retriever - Chroma vector search + BM25 keyword hybrid
"""
from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from typing import Any

import chromadb

from config import get_settings
from core import BaseRetriever, Document
from embedding import create_embedding


# ChromaDB globals
_global_client: chromadb.PersistentClient | None = None
_global_collection: chromadb.Collection | None = None


def _get_chroma_collection() -> chromadb.Collection:
    """Get or create ChromaDB collection singleton."""
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


# BM25 implementation for Chinese text
class BM25Index:
    """Simple BM25 keyword index stored in memory."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[dict] = []  # [{id, content, metadata, terms: {term: tf}}]
        self._doc_freq: dict[str, int] = defaultdict(int)
        self._avgdl: float = 0.0
        self._N: int = 0

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize Chinese text: character bigrams + words + numbers."""
        tokens = []
        # Alphanumeric tokens
        tokens.extend(re.findall(r"[a-zA-Z0-9]+", text.lower()))
        # Chinese character bigrams
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])
        # Single Chinese characters
        tokens.extend(chinese_chars)
        return tokens

    def add(self, doc_id: str, content: str, metadata: dict) -> None:
        """Add a document to the index."""
        terms = self._tokenize(content)
        tf = defaultdict(int)
        for t in terms:
            tf[t] += 1
        self._docs.append({"id": doc_id, "content": content, "metadata": metadata, "terms": dict(tf), "length": len(terms)})
        for t in set(terms):
            self._doc_freq[t] += 1
        self._N = len(self._docs)
        self._avgdl = sum(d["length"] for d in self._docs) / max(self._N, 1)

    def remove(self, doc_id: str) -> None:
        """Remove a document by ID."""
        for i, d in enumerate(self._docs):
            if d["id"] == doc_id:
                for t in d["terms"]:
                    self._doc_freq[t] -= 1
                    if self._doc_freq[t] <= 0:
                        del self._doc_freq[t]
                self._docs.pop(i)
                break
        self._N = len(self._docs)
        self._avgdl = sum(d["length"] for d in self._docs) / max(self._N, 1) if self._N > 0 else 0.0

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """Search for documents matching the query using BM25 scoring."""
        if self._N == 0:
            return []
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scores: list[tuple[str, float]] = []
        for doc in self._docs:
            score = 0.0
            for term in query_terms:
                df = self._doc_freq.get(term, 0)
                if df == 0:
                    continue
                tf = doc["terms"].get(term, 0)
                idf = math.log(1 + (self._N - df + 0.5) / (df + 0.5))
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc["length"] / max(self._avgdl, 1))
                score += idf * numerator / denominator
            if score > 0:
                scores.append((doc["id"], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @property
    def count(self) -> int:
        return self._N


# Global BM25 index
_bm25_index: BM25Index = BM25Index()


class ChromaRetriever(BaseRetriever):
    """Chroma vector + BM25 hybrid retriever."""

    def __init__(self) -> None:
        self._collection = _get_chroma_collection()
        self._embedding_fn = create_embedding()
        self._bm25 = _bm25_index

    async def retrieve(
        self, query: str, top_k: int = 5, doc_ids: list[str] | None = None
    ) -> list[Document]:
        """Hybrid retrieve: vector search + BM25 keyword search."""
        if self._collection.count() == 0:
            return []

        # Vector search: fetch more for better coverage
        vector_k = max(top_k * 3, 15)
        query_emb = await self._embedding_fn.embed_single(query)

        kwargs: dict = {
            "query_embeddings": [query_emb],
            "n_results": vector_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if doc_ids:
            kwargs["where"] = {"doc_id": {"$in": doc_ids}}

        results = self._collection.query(**kwargs)

        vec_docs: dict[str, Document] = {}
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                vec_docs[doc_id] = Document(
                    id=doc_id,
                    content=content,
                    metadata=meta or {},
                    score=1.0 - min(distance, 1.0),
                )

        # BM25 keyword search
        bm25_results = self._bm25.search(query, top_k=vector_k)
        bm25_docs: dict[str, float] = {}
        max_bm25 = max((s for _, s in bm25_results), default=1.0)
        for doc_id, score in bm25_results:
            if max_bm25 > 0:
                bm25_docs[doc_id] = score / max_bm25  # normalize to [0,1]

        # Merge: combine vector and BM25 scores
        merged: dict[str, Document] = {}
        all_ids = set(vec_docs.keys()) | set(bm25_docs.keys())

        for doc_id in all_ids:
            vec_score = vec_docs[doc_id].score if doc_id in vec_docs else 0.0
            bm25_score = bm25_docs.get(doc_id, 0.0)

            # Weighted combination: 40% BM25, 60% vector
            combined_score = vec_score * 0.6 + bm25_score * 0.4

            if doc_id in vec_docs:
                doc = vec_docs[doc_id]
                doc.score = combined_score
                merged[doc_id] = doc
            else:
                # BM25-only result: need to look up content from collection
                try:
                    res = self._collection.get(ids=[doc_id], include=["documents", "metadatas"])
                    if res["ids"]:
                        merged[doc_id] = Document(
                            id=doc_id,
                            content=res["documents"][0] if res["documents"] else "",
                            metadata=res["metadatas"][0] if res["metadatas"] else {},
                            score=combined_score,
                        )
                except Exception:
                    pass

        documents = sorted(merged.values(), key=lambda d: d.score, reverse=True)[:top_k]
        return documents

    async def add_documents(self, documents: list[Document]) -> None:
        """Batch add documents to both Chroma and BM25."""
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

        # Also add to BM25 index
        for i, doc in enumerate(documents):
            self._bm25.add(ids[i], doc.content, doc.metadata)

    async def delete(self, doc_ids: list[str]) -> None:
        """Delete documents from both stores."""
        if doc_ids:
            self._collection.delete(ids=doc_ids)
            for did in doc_ids:
                try:
                    self._bm25.remove(did)
                except Exception:
                    pass

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document."""
        try:
            results = self._collection.get(where={"doc_id": doc_id})
            ids = results.get("ids", [])
            if ids:
                self._collection.delete(ids=ids)
                for did in ids:
                    try:
                        self._bm25.remove(did)
                    except Exception:
                        pass
            return len(ids)
        except Exception:
            return 0

    async def clear_all(self) -> int:
        """Clear all documents."""
        try:
            count = self._collection.count()
            if count > 0:
                ids = self._collection.get()["ids"]
                self._collection.delete(ids=ids)
                for did in ids:
                    try:
                        self._bm25.remove(did)
                    except Exception:
                        pass
            return count
        except Exception:
            return 0

    @property
    def count(self) -> int:
        return self._collection.count()
