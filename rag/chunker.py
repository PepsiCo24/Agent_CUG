"""
RAG 文本分块器
"""
from __future__ import annotations

import re
from typing import Iterator


class TextChunker:
    """
    文本分块器
    - 按段落优先分割
    - 保持语义完整性
    - 支持重叠窗口
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " "
        ]

    def split(self, text: str) -> list[str]:
        """将文本分割为块"""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        return list(self._split_recursive(text))

    def _split_recursive(self, text: str) -> Iterator[str]:
        """递归分割"""
        if len(text) <= self.chunk_size:
            yield text
            return

        # 尝试按分隔符分割
        for sep in self.separators:
            parts = text.split(sep)
            if len(parts) > 1:
                current = ""
                for part in parts:
                    candidate = part if not current else current + sep + part

                    if len(candidate) > self.chunk_size:
                        if current:
                            yield current.strip()
                            # 重叠
                            overlap_text = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else current
                            current = overlap_text + sep + part if overlap_text else part
                        else:
                            # 单个 part 超过 chunk_size，继续递归
                            yield from self._split_recursive(part)
                    else:
                        current = candidate

                if current and current.strip():
                    yield current.strip()
                return

        # fallback: 强制按字符切分
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                yield chunk.strip()

    def split_documents(
        self, documents: list[str], metadata: dict | None = None
    ) -> list[dict[str, object]]:
        """将文档列表分割为带元数据的块"""
        chunks: list[dict[str, object]] = []
        for doc_idx, doc in enumerate(documents):
            for chunk_idx, chunk in enumerate(self.split(doc)):
                chunks.append({
                    "content": chunk,
                    "metadata": {
                        "doc_index": doc_idx,
                        "chunk_index": chunk_idx,
                        **(metadata or {}),
                    },
                })
        return chunks
