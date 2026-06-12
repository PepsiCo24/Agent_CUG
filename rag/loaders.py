"""
RAG document loader
Supports: PDF, DOCX, TXT, Markdown
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol


# Gov webpage header/footer noise patterns (line-level)
_GOV_NOISE_LINE_PATTERNS = [
    # Per-page datestamp header: "2026/6/12 00:44 doc title"
    re.compile(r'^\d{4}/\d{1,2}/\d{1,2}\s+\d{2}:\d{2}\s+'),
    # Chinese date with weekday: "2026年6月12日 星期五 ..."
    re.compile(r'^\d{4}年\d{1,2}月\d{1,2}日\s+星期'),
    # Nav bar elements
    re.compile(r'请输入关键词'),
    re.compile(r'^\s*首\s*页\s+'),
    re.compile(r'^\s*首页\s*>'),
    re.compile(r'走进\S+'),
    re.compile(r'政务动态'),
    re.compile(r'政府信息公开'),
    re.compile(r'网上服务'),
    re.compile(r'互动交流'),
    # Metadata fields
    re.compile(r'^\s*索\s*引\s*号\s*[:：]'),
    re.compile(r'^\s*信息分类\s*[:：]'),
    re.compile(r'^\s*内容分类\s*[:：]'),
    re.compile(r'^\s*发文日期\s*[:：]'),
    re.compile(r'^\s*发布机构\s*[:：]'),
    re.compile(r'^\s*生成日期\s*[:：]'),
    re.compile(r'^\s*生效日期\s*[:：]'),
    re.compile(r'^\s*废止时间\s*[:：]'),
    re.compile(r'^\s*文\s*号\s*[:：]'),
    re.compile(r'^\s*关\s*键\s*词\s*[:：]'),
    re.compile(r'^\s*内容概述\s*[:：]'),
    # Footer elements
    re.compile(r'政府网站标识码'),
    re.compile(r'主办单位[：:]'),
    re.compile(r'承办[：:]'),
    re.compile(r'鄂ICP备'),
    re.compile(r'鄂公网安备'),
    re.compile(r'www\.\w+\.\w+'),
    # Page numbers
    re.compile(r'^\d+/\d+$'),
]


def _clean_content(text: str) -> str:
    """Remove webpage header/footer noise from PDF-printed gov pages.

    Operates line-by-line: any line matching a gov-noise pattern is dropped.
    Remaining lines are reassembled and whitespace is collapsed.
    """
    lines = text.split('\n')
    kept: list[str] = []
    for line in lines:
        if any(pat.search(line) for pat in _GOV_NOISE_LINE_PATTERNS):
            continue
        kept.append(line)
    text = '\n'.join(kept)
    # Collapse multiple spaces/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


class DocumentLoader(Protocol):
    """Document loader protocol"""
    def load(self, file_path: str | Path) -> list[str]: ...


class TextLoader:
    """TXT loader"""
    def load(self, file_path: str | Path) -> list[str]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        text = _clean_content(text)
        return [text] if text.strip() else []


class MarkdownLoader:
    """Markdown loader"""
    def load(self, file_path: str | Path) -> list[str]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        text = _clean_content(text)
        return [text] if text.strip() else []


class PDFLoader:
    """PDF loader"""
    def load(self, file_path: str | Path) -> list[str]:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("Please install pdfplumber: pip install pdfplumber")

        path = Path(file_path)
        pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    cleaned = _clean_content(text.strip())
                    if cleaned:
                        pages.append(cleaned)
        return pages


class DocxLoader:
    """DOCX loader"""
    def load(self, file_path: str | Path) -> list[str]:
        try:
            import docx
        except ImportError:
            raise ImportError("Please install python-docx: pip install python-docx")

        path = Path(file_path)
        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = _clean_content("\n".join(paragraphs))
        return [text] if text else []


# Loader registry
LOADER_MAP: dict[str, DocumentLoader] = {
    ".txt": TextLoader(),
    ".md": MarkdownLoader(),
    ".markdown": MarkdownLoader(),
    ".pdf": PDFLoader(),
    ".docx": DocxLoader(),
}


def load_document(file_path: str | Path) -> list[str]:
    """Auto-select loader by file extension"""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in LOADER_MAP:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {list(LOADER_MAP.keys())}")

    return LOADER_MAP[ext].load(str(path))
