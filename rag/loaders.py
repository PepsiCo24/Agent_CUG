"""
RAG 文档加载器
支持: PDF, DOCX, TXT, Markdown
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DocumentLoader(Protocol):
    """文档加载器协议"""
    def load(self, file_path: str | Path) -> list[str]: ...


class TextLoader:
    """TXT 加载器"""
    def load(self, file_path: str | Path) -> list[str]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return [text] if text.strip() else []


class MarkdownLoader:
    """Markdown 加载器"""
    def load(self, file_path: str | Path) -> list[str]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return [text] if text.strip() else []


class PDFLoader:
    """PDF 加载器"""
    def load(self, file_path: str | Path) -> list[str]:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("请安装 pdfplumber: pip install pdfplumber")

        path = Path(file_path)
        pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
        return pages


class DocxLoader:
    """DOCX 加载器"""
    def load(self, file_path: str | Path) -> list[str]:
        try:
            import docx
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

        path = Path(file_path)
        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return ["\n".join(paragraphs)] if paragraphs else []


# 加载器注册表
LOADER_MAP: dict[str, DocumentLoader] = {
    ".txt": TextLoader(),
    ".md": MarkdownLoader(),
    ".markdown": MarkdownLoader(),
    ".pdf": PDFLoader(),
    ".docx": DocxLoader(),
}


def load_document(file_path: str | Path) -> list[str]:
    """根据文件后缀自动选择加载器"""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in LOADER_MAP:
        raise ValueError(f"不支持的文件类型: {ext}。支持: {list(LOADER_MAP.keys())}")

    return LOADER_MAP[ext].load(str(path))
