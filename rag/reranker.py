""" 
RAG reranker with Chinese bigram tokenization and article number boosting.
Improved: higher keyword weight, document name matching, Arab-Chinese digit mapping.
"""
from __future__ import annotations

import re
from core import BaseReranker, Document


def _tokenize_chinese(text: str) -> set[str]:
    """Tokenize Chinese text using character bigrams + words."""
    tokens = set()
    tokens.update(re.findall(r"[a-zA-Z0-9]+", text.lower()))
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(chinese_chars) - 1):
        tokens.add(chinese_chars[i] + chinese_chars[i + 1])
    tokens.update(chinese_chars)
    return tokens


# Chinese digit mapping for article number matching
_ARABIC_TO_CN = {
    "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}
_CN_DIGITS = "一二三四五六七八九十百千"
_CN_UNITS = "条章节部编篇"
_ARTICLE_NUM_RE = re.compile(r"第\s*[" + _CN_DIGITS + r"\d]+\s*[" + _CN_UNITS + r"]")


def _extract_article_nums(text: str) -> set[str]:
    """Extract article/chapter numbers mentioned in text.
    Returns both the original form and normalized form for matching."""
    results = set()
    for m in _ARTICLE_NUM_RE.finditer(text):
        raw = m.group()
        results.add(raw)
        # Normalize: remove spaces
        normalized = re.sub(r"\s+", "", raw)
        if normalized != raw:
            results.add(normalized)
    return results


def _ar_to_cn(num_str: str) -> str:
    """Convert Arabic numeral string to Chinese digits."""
    if not num_str.isdigit():
        return num_str
    if len(num_str) == 1:
        return _ARABIC_TO_CN.get(num_str, num_str)
    # For multi-digit: "14" -> "十四"
    result = ""
    n = len(num_str)
    for i, ch in enumerate(num_str):
        digit = _ARABIC_TO_CN.get(ch, ch)
        pos = n - i - 1  # 0=ones, 1=tens, 2=hundreds
        if pos == 1 and digit == "一":
            # "一十" -> "十"
            result += "十"
        elif pos == 1:
            result += digit + "十"
        elif pos == 2:
            result += digit + "百"
        elif pos == 0 and digit != "零":
            result += digit
        elif pos == 0:
            pass  # skip trailing zero
    return result


def _expand_query_articles(query: str) -> set[str]:
    """Expand query article numbers to cover both Arabic and Chinese forms."""
    articles = _extract_article_nums(query)
    expanded = set(articles)
    for a in articles:
        # Try to find Arabic digits in the article number
        digits = re.findall(r"\d+", a)
        for d in digits:
            cn = _ar_to_cn(d)
            if cn != d:
                cn_version = a.replace(d, cn)
                expanded.add(cn_version)
                expanded.add(re.sub(r"\s+", "", cn_version))
    return expanded


class KeywordReranker(BaseReranker):
    """Keyword-based reranker with Chinese bigram tokenization and article boosting.

    Improvements:
    - Higher keyword weight (0.55 vs 0.35)
    - Document name matching for source priority
    - Arabic-Chinese digit mapping for article queries
    - Stronger article boost (1.2 vs 0.8)
    """

    _UI_NOISE_TERMS = {
        "一一", "二三",
        "三四五六七八",
        "八九十百",
        "第一二三个",
        "四五八七八",
        "\u9996\u9875", "\u8d70\u8fdb", "\u653f\u52a1\u52a8\u6001",
        "\u653f\u5e9c\u4fe1\u606f\u516c\u5f00", "\u7f51\u4e0a\u670d\u52a1",
        "\u4e92\u52a8\u4ea4\u6d41", "\u8bf7\u8f93\u5165\u5173\u952e\u8bcd",
        "\u641c\u7d22", "\u7d22\u5f15\u53f7", "\u4e3b\u529e\u5355\u4f4d",
        "\u627f\u529e", "\u7f51\u7ad9\u6807\u8bc6\u7801",
        "\u9102ICP\u5907", "\u9102\u516c\u7f51\u5b89\u5907",
        "luotian.gov.cn", "zwgk/grassroots",
    }

    def __init__(self, keyword_weight: float = 0.55) -> None:
        self._keyword_weight = keyword_weight

    async def rerank(
        self, query: str, documents: list[Document]
    ) -> list[Document]:
        """Rerank documents by keyword overlap, article match, source name, and noise penalty."""
        if not documents:
            return []

        query_lower = query.lower()
        query_terms = _tokenize_chinese(query_lower)
        query_articles = _extract_article_nums(query)
        query_articles_expanded = _expand_query_articles(query)

        # Extract document source names for priority matching
        doc_sources = {}
        for doc in documents:
            src = doc.metadata.get("source", "")
            if src:
                # Extract the core name without extension
                name = re.sub(r"\.[^.]+$", "", src)
                doc_sources[id(doc)] = name

        for doc in documents:
            content_lower = doc.content.lower()
            content_terms = _tokenize_chinese(content_lower)

            # ----- Keyword overlap (bigram-level) -----
            if query_terms:
                overlap = len(query_terms & content_terms) / len(query_terms)
                # Scale overlap: non-linear boost for high overlap
                if overlap > 0.5:
                    overlap = min(1.0, overlap * 1.3)
            else:
                overlap = 0.0

            # ----- Exact substring match -----
            exact_bonus = 0.35 if query_lower in content_lower else 0.0

            # ----- Source document name match -----
            source_bonus = 0.0
            src_name = doc_sources.get(id(doc), "")
            if src_name and query_lower:
                # Check if query keywords appear in document name
                q_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", query_lower))
                s_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", src_name))
                if q_words and s_words:
                    src_overlap = len(q_words & s_words) / len(q_words)
                    if src_overlap > 0.3:
                        source_bonus = 0.4 * src_overlap

            # ----- Partial phrase match -----
            partial_bonus = 0.0
            query_chars = re.findall(r"[\u4e00-\u9fff]+", query_lower)
            if query_chars:
                for phrase in query_chars:
                    if len(phrase) >= 2 and phrase in content_lower:
                        partial_bonus = max(partial_bonus, 0.2)
                    # Also match individual chars spread across content
                    if len(phrase) >= 4:
                        matched = sum(1 for c in phrase if c in content_lower)
                        if matched / len(phrase) >= 0.7:
                            partial_bonus = max(partial_bonus, 0.12 * (matched / len(phrase)))

            # ----- Article number boost (enhanced) -----
            article_boost = 0.0
            if query_articles:
                content_articles = _extract_article_nums(content_lower)
                # Check original form
                if query_articles & content_articles:
                    article_boost = 1.2
                # Check expanded form (Arabic->CN)
                elif query_articles_expanded:
                    if query_articles_expanded & content_articles:
                        article_boost = 1.0

            # Also check: does query mention a number near "条"? Try direct pattern match
            if not article_boost:
                q_num_patterns = re.findall(r"\d+|第[一二三四五六七八九十百千\d]+", query)
                for p in q_num_patterns:
                    if p in content_lower:
                        article_boost = max(article_boost, 0.5)
                        break

            # ----- Website UI noise penalty -----
            noise_penalty = 0.0
            noise_hits = sum(1 for t in self._UI_NOISE_TERMS if t in content_lower)
            if noise_hits >= 3:
                noise_penalty = 0.5
            elif noise_hits >= 1:
                noise_penalty = 0.2

            # ----- Combined score -----
            keyword_score = overlap + exact_bonus + source_bonus + partial_bonus + article_boost
            # Clamp keyword score
            if keyword_score > 1.0:
                keyword_score = 1.0

            doc.score = (
                doc.score * (1 - self._keyword_weight)
                + keyword_score * self._keyword_weight
                - noise_penalty
            )
            # Clamp final score
            if doc.score > 1.0:
                doc.score = 1.0
            if doc.score < 0.0:
                doc.score = 0.0

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents
