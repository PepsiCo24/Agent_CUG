"""
RAG Gateway v4 - Hybrid retrieval + cleaned PDF extraction
"""

import os, re, uuid, hashlib, requests
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

QDRANT_PATH = Path(os.environ.get("QDRANT_PATH", "./qdrant-data"))
EMBEDDING_KEY = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_BASE = os.environ.get("EMBEDDING_BASE_URL", "https://api.siliconflow.cn")
EMBEDDING_MODEL = "BAAI/bge-m3"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
EMBEDDING_DIM = 1024
CHUNK_SIZE = 800
TOP_K = 8
SERVER_PORT = int(os.environ.get("RAG_GATEWAY_PORT", "3001"))

app = FastAPI(title="RAG Gateway v4", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_qdrant_client = None

def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=str(QDRANT_PATH))
    return _qdrant_client

def ensure_collection(kb_id: str):
    client = get_qdrant()
    name = f"kb_{kb_id}"
    from qdrant_client.models import Distance, VectorParams
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    return name

def embed_texts(texts):
    resp = requests.post(
        f"{EMBEDDING_BASE}/v1/embeddings",
        headers={"Authorization": f"Bearer {EMBEDDING_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": texts, "encoding_format": "float"},
        timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

def clean_text(text: str) -> str:
    """Clean PDF extraction artifacts."""
    if not text:
        return ""
    # Remove null bytes
    text = text.replace('\x00', '')
    # Remove (cid:N) markers
    text = re.sub(r'\(cid:\d+\)', '', text)
    # Remove other control characters except newlines
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r' {3,}', '  ', text)
    # Fix common PDF word-break artifacts (hyphenated words across lines)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    return text.strip()

def parse_pdf_file(file_path: str) -> str:
    """Extract text from PDF. PyPDF2 first (fewer artifacts), pdfplumber fallback."""
    text = ""

    # Try PyPDF2 first - better for Chinese PDFs with embedded fonts
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            text = "\n\n".join(text_parts)
            text = clean_text(text)
            if len(text) > 100:
                return text
    except Exception as e:
        print(f"PyPDF2 failed: {e}")

    # Fallback to pdfplumber
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    # Clean page-level artifacts
                    page_text = clean_text(page_text)
                    text_parts.append(page_text)
        if text_parts:
            text = "\n\n".join(text_parts)
    except Exception as e:
        print(f"pdfplumber failed: {e}")

    return text.strip()

def parse_docx_file(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return clean_text(text)
    except Exception as e:
        print(f"python-docx failed: {e}")
        return ""

def chunk_text(text, size=CHUNK_SIZE):
    """Chunk text preserving article boundaries for Chinese legal documents."""
    if not text or not text.strip():
        return []
    # Split by article markers
    article_pattern = r'(?=第[一二三四五六七八九十百]+条)'
    articles = re.split(article_pattern, text)
    chunks = []
    for article in articles:
        article = article.strip()
        if not article:
            continue
        if len(article) <= size * 2:
            if len(article) <= size:
                chunks.append(article)
            else:
                sentences = re.split(r'(?<=[.。！？!?])\s*', article)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) <= size:
                        current += sent
                    else:
                        if current.strip():
                            chunks.append(current.strip())
                        current = sent
                if current.strip():
                    chunks.append(current.strip())
        else:
            paragraphs = re.split(r"\n\s*\n", article)
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(para) <= size:
                    chunks.append(para)
                else:
                    sentences = re.split(r'(?<=[.。！？!?])\s*', para)
                    current = ""
                    for sent in sentences:
                        if len(current) + len(sent) <= size:
                            current += sent
                        else:
                            if current.strip():
                                chunks.append(current.strip())
                            current = sent
                    if current.strip():
                        chunks.append(current.strip())
    # Merge small adjacent chunks
    merged, buf = [], ""
    for c in chunks:
        if len(buf) + len(c) <= size:
            buf = (buf + "\n\n" + c).strip() if buf else c
        else:
            if buf:
                merged.append(buf)
            buf = c
    if buf:
        merged.append(buf)
    return merged

_CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
           '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,'十六':16,'十七':17,'十八':18,'十九':19,'二十':20}

def extract_article_numbers(query: str) -> list:
    matches = re.findall(r'第([一二三四五六七八九十百]+)条', query)
    result = []
    for m in matches:
        result.append(f'第{m}条')
        if m in _CN_NUM:
            result.append(str(_CN_NUM[m]))
    return result

def keyword_match_score(chunk_text: str, article_nums: list) -> float:
    if not article_nums:
        return 0.0
    score = 0.0
    for an in article_nums:
        if an in chunk_text:
            score += 0.5
        if chunk_text.strip().startswith(an):
            score += 1.0
    return min(score, 1.0)

def hybrid_search(query: str, query_embedding: list, collection_name: str, top_k: int = TOP_K):
    client = get_qdrant()
    all_points, _ = client.scroll(collection_name=collection_name, limit=2000, with_payload=True, with_vectors=True)

    def cosine(a, b):
        dot = sum(x*y for x,y in zip(a,b))
        na = sum(x*x for x in a)**0.5
        nb = sum(x*x for x in b)**0.5
        return dot/(na*nb) if na*nb > 0 else 0

    article_nums = extract_article_numbers(query)

    scored = []
    for p in all_points:
        if not p.vector:
            continue
        vec_score = cosine(query_embedding, p.vector)
        kw_score = keyword_match_score(p.payload.get("text", ""), article_nums)
        if article_nums:
            final = vec_score * 0.65 + kw_score * 0.35
        else:
            final = vec_score
        scored.append((final, p, vec_score, kw_score))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


class ParseRequest(BaseModel):
    file_path: str; file_type: str

class ParseResponse(BaseModel):
    success: bool; markdown: str; char_count: int

class EmbedRequest(BaseModel):
    kb_id: str; document_name: str; markdown_content: str

class EmbedResponse(BaseModel):
    doc_id: str; chunks_count: int; status: str

class ChatRequest(BaseModel):
    kb_id: str; question: str; history: list[dict] = []

class Citation(BaseModel):
    document_name: str; snippet: str; score: float

class ChatResponse(BaseModel):
    answer: str; citations: list[Citation]; conversation_id: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-gateway-v4"}

@app.get("/api/ping")
def ping():
    return {"status": "ok"}

@app.post("/api/rag/parse", response_model=ParseResponse)
def parse_document(req: ParseRequest):
    fp = req.file_path; ft = req.file_type.upper() if req.file_type else ""; text = ""
    try:
        if not os.path.exists(fp):
            return ParseResponse(success=False, markdown="", char_count=0)
        if ft in ("PDF",):
            text = parse_pdf_file(fp)
        elif ft in ("WORD", "DOCX"):
            text = parse_docx_file(fp)
        elif ft in ("TXT", "MARKDOWN", "MD"):
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                text = clean_text(f.read())
        if not text or not text.strip():
            return ParseResponse(success=False, markdown="", char_count=0)
        md = f"# {os.path.basename(fp)}\n\n{text}"
        return ParseResponse(success=True, markdown=md, char_count=len(md))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rag/embed", response_model=EmbedResponse)
def embed_document(req: EmbedRequest):
    try:
        client = get_qdrant()
        collection = ensure_collection(req.kb_id)
        chunks = chunk_text(req.markdown_content)
        if not chunks:
            chunks = [req.markdown_content[:CHUNK_SIZE]]
        print(f"[Embed] {len(chunks)} chunks from {len(req.markdown_content)} chars")
        all_embeddings = []
        for i in range(0, len(chunks), 32):
            all_embeddings.extend(embed_texts(chunks[i:i+32]))
        doc_id = str(uuid.uuid4())
        from qdrant_client.models import PointStruct
        points = []
        for i, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
            points.append(PointStruct(
                id=hashlib.md5(f"{doc_id}_{i}".encode()).hexdigest(),
                vector=emb,
                payload={"doc_id": doc_id, "document_name": req.document_name,
                         "chunk_index": i, "text": chunk}))
        for i in range(0, len(points), 100):
            client.upsert(collection_name=collection, points=points[i:i+100])
        return EmbedResponse(doc_id=doc_id, chunks_count=len(chunks), status="COMPLETED")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rag/chat", response_model=ChatResponse)
def rag_chat(req: ChatRequest):
    try:
        client = get_qdrant()
        collection = f"kb_{req.kb_id}"
        if not client.collection_exists(collection):
            return ChatResponse(answer="Knowledge base is empty. Please upload documents first.",
                               citations=[], conversation_id="default")

        q_emb = embed_texts([req.question])[0]
        top = hybrid_search(req.question, q_emb, collection, top_k=TOP_K)

        article_nums = extract_article_numbers(req.question)
        if article_nums:
            print(f"[Hybrid] Article numbers: {article_nums}")

        parts = []
        for final_score, point, vec_score, kw_score in top:
            txt = point.payload.get("text", "")
            dn = point.payload.get("document_name", "Unknown")
            tag = " [ARTICLE]" if kw_score > 0 else ""
            parts.append(f"[Source: {dn}{tag} | score={final_score:.3f}]\n{txt}")
            print(f"  [{dn}] v={vec_score:.3f} kw={kw_score:.2f} final={final_score:.3f}: {txt[:80]}...")

        citations = [
            Citation(document_name=point.payload.get("document_name",""),
                     snippet=point.payload.get("text","")[:300],
                     score=round(final_score, 4))
            for final_score, point, _, _ in top
        ]

        prompt = (
            "You are a precise document-based assistant for Chinese legal documents. "
            "Answer strictly based on the documents provided below. "
            "If the answer is not in the documents, say so clearly. "
            "Always cite the specific article number and quote the exact text.\n\n"
            "Documents:\n" + "\n\n---\n\n".join(parts)
        )

        messages = [{"role": "system", "content": prompt}]
        for h in req.history:
            role = h.get("role", "user")
            content = h.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": req.question})

        resp = requests.post(
            f"{DEEPSEEK_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.3, "max_tokens": 4096},
            timeout=120)
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
        return ChatResponse(answer=answer, citations=citations, conversation_id="default")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/rag/clear-kb/{kb_id}")
def clear_kb(kb_id: str):
    try:
        client = get_qdrant()
        collection = f"kb_{kb_id}"
        if client.collection_exists(collection):
            client.delete_collection(collection)
            return {"status": "ok", "message": f"Cleared {collection}"}
        return {"status": "ok", "message": "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"RAG Gateway v4 | Hybrid Search | Port: {SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")