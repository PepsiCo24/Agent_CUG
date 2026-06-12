"""
RAG document loader
Supports: PDF, DOCX, TXT, Markdown
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol


# Common webpage noise patterns in PDF printouts
_NOISE_PATTERNS = [
    re.compile(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{2}:\d{2}\s+'),  # datetime stamps
    re.compile(r'www\.[a-z]+\.[a-z]+(?:\.cn)?/[^\s]*'),  # URLs
    re.compile(r'https?://[^\s]+'),  # http URLs
    re.compile(r'\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5\s*\u661f\u671f[\u4e00-\u9fff]'),  # Chinese date
    re.compile(r'^\s*(?:\u9996\s*\u9875|\u8d70\u8fdb|\u8bf7\u8f93\u5165|\u5173\u952e\u8bcd|\u641c\u7d22)\s*$', re.MULTILINE),
]


def _clean_content(text: str) -> str:
    """Remove common webpage noise from extracted text."""
    for pat in _NOISE_PATTERNS:
        text = pat.sub(' ', text)
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
