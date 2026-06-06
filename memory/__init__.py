"""
Memory 系统 — 短期记忆（SQLite）+ 长期记忆（Chroma）
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import get_settings
from core import BaseMemory, MemoryItem


# 全局 ChromaDB 单例（避免重复创建 PersistentClient）
_global_memory_chroma_client = None
_global_memory_chroma_collection = None
_global_memory_embedding_fn = None

class MemoryManager(BaseMemory):
    """
    统一记忆管理器
    - 短期记忆：SQLite，最近 N 条消息
    - 长期记忆：Chroma 向量检索 + SQLite 元数据
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._short_term_max = settings.memory.SHORT_TERM_MAX
        self._long_term_ttl_days = settings.memory.LONG_TERM_TTL_DAYS

        db_path = settings.resolve_path(settings.sqlite.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

        # 延迟导入 embedding 避免循环依赖
        self._embedding_fn = None
        self._chroma_collection = None
        self._chroma_ready = False

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS short_term_memory (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS long_term_memory (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                embedding_id TEXT,
                importance REAL DEFAULT 0.5,
                ttl INTEGER,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_stm_created
                ON short_term_memory(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ltm_created
                ON long_term_memory(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ltm_importance
                ON long_term_memory(importance DESC);
        """)
        self._conn.commit()

    async def _ensure_chroma(self) -> None:
        """延迟初始化 Chroma（使用全局单例避免重复创建）"""
        global _global_memory_chroma_client, _global_memory_chroma_collection, _global_memory_embedding_fn

        if self._chroma_ready:
            return

        import chromadb
        from embedding import create_embedding

        if _global_memory_chroma_collection is None:
            settings = get_settings()
            chroma_dir = settings.resolve_path(settings.chroma.PERSIST_DIR)
            chroma_dir.mkdir(parents=True, exist_ok=True)
            _global_memory_chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
            _global_memory_chroma_collection = _global_memory_chroma_client.get_or_create_collection(
                name="agent_cug_memory",
                metadata={"hnsw:space": "cosine"},
            )
            _global_memory_embedding_fn = create_embedding()

        self._chroma_client = _global_memory_chroma_client
        self._chroma_collection = _global_memory_chroma_collection
        self._embedding_fn = _global_memory_embedding_fn
        self._chroma_ready = True

    # ---- Short-Term Memory ----

    async def add(self, item: MemoryItem) -> str:
        """添加短期记忆"""
        if not item.id:
            item.id = str(uuid.uuid4())

        self._conn.execute(
            """INSERT OR REPLACE INTO short_term_memory
               (id, content, role, importance, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                item.id,
                item.content,
                item.role,
                item.importance,
                item.created_at.isoformat(),
                _safe_json(item.metadata),
            ),
        )
        self._conn.commit()
        self._trim_short_term()

        # 同时写入长期记忆（异步）
        await self._add_long_term(item)

        return item.id

    def _trim_short_term(self) -> None:
        """裁剪短期记忆到最大数量"""
        self._conn.execute(
            """DELETE FROM short_term_memory WHERE id NOT IN (
                SELECT id FROM short_term_memory
                ORDER BY created_at DESC LIMIT ?
            )""",
            (self._short_term_max,),
        )
        self._conn.commit()

    async def get_recent(self, limit: int = 20) -> list[MemoryItem]:
        """获取最近短期记忆"""
        rows = self._conn.execute(
            "SELECT * FROM short_term_memory ORDER BY created_at DESC LIMIT ?",
            (min(limit, self._short_term_max),),
        ).fetchall()
        return [_row_to_item(r) for r in reversed(rows)]

    # ---- Long-Term Memory ----

    async def _add_long_term(self, item: MemoryItem) -> None:
        """添加长期记忆（含向量）"""
        await self._ensure_chroma()

        embedding = item.embedding
        if embedding is None and self._embedding_fn and item.content.strip():
            embedding = await self._embedding_fn.embed_single(item.content)

        embedding_id = None
        if embedding and self._chroma_collection:
            embedding_id = item.id
            self._chroma_collection.upsert(
                ids=[embedding_id],
                embeddings=[embedding],
                metadatas=[{
                    "role": item.role,
                    "importance": item.importance,
                    "created_at": item.created_at.isoformat(),
                }],
                documents=[item.content],
            )

        self._conn.execute(
            """INSERT OR REPLACE INTO long_term_memory
               (id, content, role, embedding_id, importance, ttl, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.id,
                item.content,
                item.role,
                embedding_id,
                item.importance,
                item.ttl or self._long_term_ttl_days,
                item.created_at.isoformat(),
                _safe_json(item.metadata),
            ),
        )
        self._conn.commit()

    async def retrieve(
        self, query: str, top_k: int = 5
    ) -> list[MemoryItem]:
        """检索相关长期记忆"""
        await self._ensure_chroma()

        if not self._chroma_collection or not self._embedding_fn:
            return []

        query_emb = await self._embedding_fn.embed_single(query)

        results = self._chroma_collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        items: list[MemoryItem] = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                content = (
                    results["documents"][0][i]
                    if results["documents"]
                    else ""
                )
                items.append(MemoryItem(
                    id=mem_id,
                    content=content,
                    role=results["metadatas"][0][i].get("role", "user") if results["metadatas"] else "user",
                    importance=float(
                        results["metadatas"][0][i].get("importance", 0.5)
                    ) if results["metadatas"] else 0.5,
                ))

        return items

    async def score(self, item_id: str, importance: float) -> None:
        """更新重要性评分"""
        self._conn.execute(
            "UPDATE long_term_memory SET importance = ? WHERE id = ?",
            (max(0.0, min(1.0, importance)), item_id),
        )
        self._conn.execute(
            "UPDATE short_term_memory SET importance = ? WHERE id = ?",
            (max(0.0, min(1.0, importance)), item_id),
        )
        self._conn.commit()

    async def deduplicate(self, threshold: float = 0.95) -> int:
        """基于内容相似度去重"""
        await self._ensure_chroma()

        # 简单实现：按内容精确匹配去重
        cursor = self._conn.execute(
            """DELETE FROM long_term_memory WHERE id IN (
                SELECT id FROM long_term_memory
                GROUP BY content HAVING COUNT(*) > 1
            )"""
        )
        self._conn.commit()
        return cursor.rowcount

    async def cleanup_expired(self) -> int:
        """清理过期长期记忆"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self._long_term_ttl_days)).isoformat()

        # 先获取过期 ID
        expired = self._conn.execute(
            "SELECT id, embedding_id FROM long_term_memory WHERE created_at < ?",
            (cutoff,),
        ).fetchall()

        # 从 Chroma 删除
        if expired and self._chroma_collection:
            await self._ensure_chroma()
            chroma_ids = [r["embedding_id"] for r in expired if r["embedding_id"]]
            if chroma_ids:
                self._chroma_collection.delete(ids=chroma_ids)

        # 从 SQLite 删除
        cursor = self._conn.execute(
            "DELETE FROM long_term_memory WHERE created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cursor.rowcount


# ---- Helpers ----

def _row_to_item(row: sqlite3.Row) -> MemoryItem:
    import json as _json
    meta = row["metadata"]
    if isinstance(meta, str):
        try:
            meta = _json.loads(meta)
        except (json.JSONDecodeError, TypeError):
            meta = {}

    return MemoryItem(
        id=row["id"],
        content=row["content"],
        role=row["role"],
        importance=float(row["importance"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        metadata=meta if isinstance(meta, dict) else {},
    )


def _safe_json(obj: Any) -> str:
    import json as _json
    if obj is None:
        return "{}"
    if isinstance(obj, str):
        return obj
    return _json.dumps(obj, ensure_ascii=False, default=str)
