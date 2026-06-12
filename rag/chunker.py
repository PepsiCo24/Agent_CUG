"""
RAG text chunker with article-aware splitting for Chinese legal documents.
"""
from __future__ import annotations

import re
from typing import Iterator


class TextChunker:
    """Text chunker with article-aware splitting."""

    _CN_DIGITS = chr(0x4e00) + chr(0x4e8c) + chr(0x4e09) + chr(0x56db) + chr(0x4e94) + chr(0x516d) + chr(0x4e03) + chr(0x516b) + chr(0x4e5d) + chr(0x5341) + chr(0x767e) + chr(0x5343)
    _CN_UNITS = chr(0x6761) + chr(0x7ae0) + chr(0x8282) + chr(0x90e8) + chr(0x7f16) + chr(0x7bc7)

    _ARTICLE_RE = re.compile(
        chr(0x7b2c) + r"\s*[" + _CN_DIGITS + r"\d]+\s*[" + _CN_UNITS + r"]"
    )

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        article_aware: bool = True,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.article_aware = article_aware
        self.separators = separators or [
            chr(10) + chr(10), chr(10),  # newlines
            chr(0x3002), chr(0xff01), chr(0xff1f),  # Chinese punctuation
            ".", "!", "?",
            chr(0xff1b), ";", " "
        ]

    def _pre_split_articles(self, text: str) -> list[str]:
        """Pre-split by article boundaries to keep each article intact."""
        matches = list(self._ARTICLE_RE.finditer(text))
        if len(matches) <= 1:
            return [text]

        segments = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)

        if matches and matches[0].start() > 0:
            preamble = text[:matches[0].start()].strip()
            if preamble:
                segments.insert(0, preamble)

        return segments if segments else [text]

    def split(self, text: str) -> list[str]:
        """Split text into chunks."""
        if not text or not text.strip():
            return []

        if len(text) <= self.chunk_size:
            return [text.strip()]

        if self.article_aware:
            articles = self._pre_split_articles(text)
            if len(articles) > 1:
                chunks = []
                for article in articles:
                    if len(article) <= self.chunk_size:
                        if article.strip():
                            chunks.append(article.strip())
                    else:
                        chunks.extend(self._split_recursive(article))
                return chunks

        return list(self._split_recursive(text))

    def _split_recursive(self, text: str) -> Iterator[str]:
        """Recursive splitting by separators."""
        if len(text) <= self.chunk_size:
            yield text
            return

        for sep in self.separators:
            parts = text.split(sep)
            if len(parts) > 1:
                current = ""
                for part in parts:
                    candidate = part if not current else current + sep + part
                    if len(candidate) > self.chunk_size:
                        if current:
                            yield current.strip()
                            overlap_text = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else current
                            current = overlap_text + sep + part if overlap_text else part
                        else:
                            yield from self._split_recursive(part)
                    else:
                        current = candidate
                if current and current.strip():
                    yield current.strip()
                return

        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                yield chunk.strip()

    def split_documents(
        self, documents: list[str], metadata: dict | None = None
    ) -> list[dict[str, object]]:
        """Split documents into chunks with metadata."""
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
