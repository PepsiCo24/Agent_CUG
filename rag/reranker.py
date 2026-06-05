"""
RAG 重排序器
"""
from __future__ import annotations

from core import BaseReranker, Document


class KeywordReranker(BaseReranker):
    """
    基于关键词匹配的重排序器
    不需要额外 API 调用，轻量级实现
    """

    def __init__(self, keyword_weight: float = 0.3) -> None:
        self._keyword_weight = keyword_weight

    async def rerank(
        self, query: str, documents: list[Document]
    ) -> list[Document]:
        """基于关键词匹配重新排序"""
        if not documents:
            return []

        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for doc in documents:
            content_lower = doc.content.lower()
            content_terms = set(content_lower.split())

            # 关键词重叠比例
            if query_terms:
                overlap = len(query_terms & content_terms) / len(query_terms)
            else:
                overlap = 0.0

            # 精确子串匹配加分
            exact_bonus = 0.2 if query_lower in content_lower else 0.0

            # 组合分数：70% 向量相似度 + 30% 关键词匹配
            doc.score = (
                doc.score * (1 - self._keyword_weight)
                + (overlap + exact_bonus) * self._keyword_weight
            )

        # 按分数降序排列
        documents.sort(key=lambda d: d.score, reverse=True)
        return documents
