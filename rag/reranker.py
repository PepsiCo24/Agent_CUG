"""
RAG reranker with Chinese bigram tokenization and article number boosting.
"""
from __future__ import annotations

import re
from core import BaseReranker, Document


def _tokenize_chinese(text: str) -> set[str]:
    """Tokenize Chinese text using character bigrams."""
    tokens = set()
    tokens.update(re.findall(r'[a-zA-Z0-9]+', text.lower()))
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    for i in range(len(chinese_chars) - 1):
        tokens.add(chinese_chars[i] + chinese_chars[i + 1])
    tokens.update(chinese_chars)
    return tokens


# Pattern for Chinese article numbers
_CN_DIGITS = '一二三四五六七八九十百千'
_CN_UNITS = '条章节部编篇'
_ARTICLE_NUM_RE = re.compile(
    '第\\s*[' + _CN_DIGITS + '\\d]+\\s*[' + _CN_UNITS + ']'
)


def _extract_article_nums(text: str) -> set[str]:
    """Extract article/chapter numbers mentioned in text."""
    return set(m.group() for m in _ARTICLE_NUM_RE.finditer(text))


class KeywordReranker(BaseReranker):
    """Keyword-based reranker with Chinese bigram tokenization and article boosting."""

    _UI_NOISE_TERMS = {
        '一一', '二三',
        '三四五六七',
        '八九十百',
        '第一二三',
        '四五六七八',
        '\u9996\u9875', '\u8d70\u8fdb', '\u653f\u52a1\u52a8\u6001',
        '\u653f\u5e9c\u4fe1\u606f\u516c\u5f00', '\u7f51\u4e0a\u670d\u52a1',
        '\u4e92\u52a8\u4ea4\u6d41', '\u8bf7\u8f93\u5165\u5173\u952e\u8bcd',
        '\u641c\u7d22', '\u7d22\u5f15\u53f7', '\u4e3b\u529e\u5355\u4f4d',
        '\u627f\u529e', '\u7f51\u7ad9\u6807\u8bc6\u7801',
        '\u9102ICP\u5907', '\u9102\u516c\u7f51\u5b89\u5907',
    }

    def __init__(self, keyword_weight: float = 0.35) -> None:
        self._keyword_weight = keyword_weight

    async def rerank(
        self, query: str, documents: list[Document]
    ) -> list[Document]:
        """Rerank documents by keyword overlap, article match, and noise penalty."""
        if not documents:
            return []

        query_lower = query.lower()
        query_terms = _tokenize_chinese(query_lower)
        query_articles = _extract_article_nums(query)

        for doc in documents:
            content_lower = doc.content.lower()
            content_terms = _tokenize_chinese(content_lower)

            # Keyword overlap ratio
            if query_terms:
                overlap = len(query_terms & content_terms) / len(query_terms)
            else:
                overlap = 0.0

            # Exact substring match
            exact_bonus = 0.25 if query_lower in content_lower else 0.0

            # Partial phrase match
            partial_bonus = 0.0
            query_chars = re.findall(r'[\u4e00-\u9fff]+', query_lower)
            if query_chars:
                for phrase in query_chars:
                    if len(phrase) >= 2 and phrase in content_lower:
                        partial_bonus = max(partial_bonus, 0.15)

            # Article number boost
            article_boost = 0.0
            if query_articles:
                content_articles = _extract_article_nums(content_lower)
                if query_articles & content_articles:
                    article_boost = 0.8

            # Website UI noise penalty
            noise_penalty = 0.0
            noise_hits = sum(1 for t in self._UI_NOISE_TERMS if t in content_lower)
            if noise_hits >= 3:
                noise_penalty = 0.4
            elif noise_hits >= 1:
                noise_penalty = 0.15

            # Combined score
            doc.score = (
                doc.score * (1 - self._keyword_weight)
                + (overlap + exact_bonus + partial_bonus + article_boost) * self._keyword_weight
                - noise_penalty
            )
            if doc.score > 1.0:
                doc.score = 1.0
            if doc.score < 0.0:
                doc.score = 0.0

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents
