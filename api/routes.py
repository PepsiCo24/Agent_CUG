"""API Routes - FastAPI with user/device isolation"""
from __future__ import annotations
import json as _json, logging, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sse_starlette.sse import EventSourceResponse
from agent import get_agent
from api.schemas import ChatRequest, ChatResponse, FileUploadResponse, HealthResponse, HistoryItem, HistoryResponse, MigrateRequest, RAGQueryRequest, RAGQueryResponse
from config import get_settings
from rag import RAGPipeline
from auth import get_current_user, UserInfo
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
HISTORY_FILE = Path("./data/history.json")
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOC_STORE_FILE = Path("./data/documents.json")
DOC_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_history_store() -> dict:
    if HISTORY_FILE.exists():
        try:
            return _json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError) as e:
            logger.warning(f"load history failed: {e}")
    return {}


def _save_history_store(store: dict) -> None:
    try:
        HISTORY_FILE.write_text(_json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error(f"save history failed: {e}")


def _load_doc_store() -> dict:
    if DOC_STORE_FILE.exists():
        try:
            return _json.loads(DOC_STORE_FILE.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_doc_store(store: dict) -> None:
    DOC_STORE_FILE.write_text(_json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


_doc_store: dict = _load_doc_store()


def _reload_docs() -> None:
    global _doc_store
    _doc_store = _load_doc_store()

_history_store: dict = _load_history_store()
# auto-migrate on startup
if _history_store:
    _tmp_changed = False
    for _cid, _e in list(_history_store.items()):
        if isinstance(_e, list):
            _history_store[_cid] = {"messages": _e, "title": "", "_owner_type": "none", "_owner_id": "legacy"}
            _tmp_changed = True
        elif isinstance(_e, dict) and (not _e.get("_owner_type")):
            _e["_owner_type"] = "none"
            _e["_owner_id"] = "legacy"
            _tmp_changed = True
    if _tmp_changed:
        _save_history_store(_history_store)

def _reload() -> None:
    global _history_store
    _history_store = _load_history_store()


def _resolve_scope(request: Request):
    try:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            from auth import decode_jwt
            p = decode_jwt(ah[7:])
            if p:
                return ("user", p["sub"])
    except Exception:
        pass
    did = request.query_params.get("device_id") or request.headers.get("X-Device-Id") or ""
    if did:
        return ("device", did)
    return ("none", "")


def _get_scoped_conversations(st: str, sid: str) -> dict:
    _reload()
    result = {}
    if not _history_store:
        return result
    for cid, e in _history_store.items():
        if isinstance(e, list):
            # old list format: upgrade to dict with legacy owner
            _history_store[cid] = {"messages": e, "title": "", "_owner_type": "none", "_owner_id": "legacy"}
            e = _history_store[cid]
        if isinstance(e, dict):
            ot = e.get("_owner_type", "")
            oi = e.get("_owner_id", "")
            # auto-fill missing _owner_type
            if not ot:
                e["_owner_type"] = "none"
                e["_owner_id"] = "legacy"
                ot, oi = "none", "legacy"
            if ot == st and oi == sid:
                result[cid] = e
    return result


def _gm(e) -> list:
    if isinstance(e, list): return e
    if isinstance(e, dict) and "messages" in e: return e["messages"]
    return []


def _gt(e, msgs) -> str:
    if isinstance(e, dict):
        t = e.get("title", "")
        if t: return t
    if msgs: return msgs[0].get("content", "New Chat")[:30]
    return "New Chat"


def _migrate_legacy() -> None:
    _reload()
    changed = False
    for cid, e in list(_history_store.items()):
        if isinstance(e, list):
            _history_store[cid] = {"messages": e, "title": "", "_owner_type": "none", "_owner_id": "legacy"}
            changed = True
        elif isinstance(e, dict):
            if "_owner_type" not in e or not e.get("_owner_type"):
                e["_owner_type"] = "none"
                e["_owner_id"] = "legacy"
                changed = True
    if changed:
        _save_history_store(_history_store)


@router.get("/auth/me")
async def auth_me(user: UserInfo | None = Depends(get_current_user)):
    if user:
        return {"authenticated": True, "user": user.model_dump()}
    return {"authenticated": False, "user": None}


@router.get("/health", response_model=HealthResponse)
async def health():
    import time
    start = time.time()
    dc = RAGPipeline().document_count
    elapsed = round((time.time() - start) * 1000, 2)
    return HealthResponse(status="ok", version="1.0.0", document_count=dc, metadata={"response_ms": elapsed})


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Chat endpoint - supports mode: chat/rag/tool/orchestrate"""
    user_input = request.message or request.user_input or ""
    mode = request.mode or "chat"
    agent = get_agent()
    cid = request.conversation_id or str(uuid.uuid4())
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="message empty")
    agent = get_agent()
    cid = request.conversation_id or str(uuid.uuid4())
    st, sid = _resolve_scope(req)
    if st == "none" and request.device_id:
        st, sid = "device", request.device_id
    try:
        result = await agent.run(user_input, cid, doc_ids=request.doc_ids, mode=mode)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    _reload(); _migrate_legacy()
    if cid not in _history_store:
        _history_store[cid] = {"messages": [], "title": "", "_owner_type": st, "_owner_id": sid, "created_at": datetime.now(timezone.utc).isoformat()}
    entry = _history_store[cid]
    if isinstance(entry, list):
        entry = {"messages": entry, "title": "", "_owner_type": st, "_owner_id": sid}
        _history_store[cid] = entry
    msgs = _gm(entry)
    msgs.append({"role": "user", "content": request.message})
    msgs.append({"role": "assistant", "content": result.get("final_answer", "")})
    entry["messages"] = msgs
    _save_history_store(_history_store)
    sources = []
    if result.get("retrieved_docs"):
        for doc in result["retrieved_docs"]:
            sources.append({"source": doc.metadata.get("source", "unknown"), "content": doc.content[:200]})
    return ChatResponse(conversation_id=cid, answer=result.get("final_answer", ""), sources=sources)

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Streaming chat endpoint with SSE - supports all agent modes"""
    user_input = request.message or request.user_input or ""
    mode = request.mode or "chat"
    if not user_input or not user_input.strip():
        raise HTTPException(status_code=422, detail="message empty")

    agent = get_agent()
    cid = request.conversation_id or str(uuid.uuid4())
    st, sid = _resolve_scope(req)
    if st == "none" and request.device_id:
        st, sid = "device", request.device_id

    async def event_generator():
        try:
            full_answer = ""
            async for token in agent.run_stream(
                user_input, cid, doc_ids=request.doc_ids, mode=mode
            ):
                # Parse JSON metadata tokens and send as proper event types
                if token.startswith("{") and '"type"' in token:
                    import json as _json
                    try:
                        meta = _json.loads(token)
                        if meta.get("type") == "rag_docs":
                            yield {"event": "rag_docs", "data": _json.dumps(meta.get("documents", []))}
                        elif meta.get("type") == "tool_call":
                            yield {"event": "tool_call", "data": _json.dumps({"name": meta.get("name", ""), "result": meta.get("result", "")})}
                        else:
                            yield {"event": "metadata", "data": token}
                    except Exception:
                        yield {"event": "metadata", "data": token}
                else:
                    full_answer += token
                    yield {"event": "token", "data": token}

            # Save to history
            _reload(); _migrate_legacy()
            if cid not in _history_store:
                _history_store[cid] = {
                    "messages": [], "title": user_input[:30],
                    "_owner_type": st, "_owner_id": sid,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            entry = _history_store[cid]
            if isinstance(entry, list):
                entry = {"messages": entry, "title": user_input[:30], "_owner_type": st, "_owner_id": sid}
                _history_store[cid] = entry
            msgs = _gm(entry)
            msgs.append({"role": "user", "content": user_input})
            msgs.append({"role": "assistant", "content": full_answer})
            entry["messages"] = msgs
            _save_history_store(_history_store)

            # Send done event with conversation_id
            import json as _json
            yield {"event": "done", "data": _json.dumps({"conversation_id": cid, "full_answer": full_answer})}

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())



@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="message empty")
    agent = get_agent()
    cid = request.conversation_id or str(uuid.uuid4())
    st, sid = _resolve_scope(req)
    if st == "none" and request.device_id:
        st, sid = "device", request.device_id

    async def event_generator():
        fa = ""
        try:
            _reload(); _migrate_legacy()
            if cid not in _history_store:
                _history_store[cid] = {"messages": [], "title": "", "_owner_type": st, "_owner_id": sid, "created_at": datetime.now(timezone.utc).isoformat()}
            entry = _history_store[cid]
            if isinstance(entry, list):
                entry = {"messages": entry, "title": "", "_owner_type": st, "_owner_id": sid, "created_at": datetime.now(timezone.utc).isoformat()}
                _history_store[cid] = entry
            entry["messages"] = _gm(entry) + [{"role": "user", "content": request.message}]
            _save_history_store(_history_store)
            async for chunk in agent.run_stream(request.message, cid, doc_ids=request.doc_ids):
                if chunk.startswith('{"type": "rag_docs"'):
                    try:
                        rd = _json.loads(chunk)
                        yield {"event": "rag_docs", "data": _json.dumps(rd.get("documents", []))}
                    except _json.JSONDecodeError: pass
                elif chunk.startswith('{"type": "tool_call"'):
                    try:
                        tc = _json.loads(chunk)
                        yield {"event": "tool_call", "data": _json.dumps({"name": tc.get("name","?"), "arguments": tc.get("arguments",{})})}
                    except _json.JSONDecodeError: pass
                else:
                    fa += chunk
                    yield {"event": "token", "data": chunk}
            _reload()
            entry = _history_store.get(cid)
            if entry:
                msgs = _gm(entry)
                msgs.append({"role": "assistant", "content": fa})
                entry["messages"] = msgs
                _save_history_store(_history_store)
            yield {"event": "done", "data": _json.dumps({"conversation_id": cid, "full_answer": fa})}
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": str(e)}
    return EventSourceResponse(event_generator())


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    rag = RAGPipeline()
    if request.doc_ids:
        docs = await rag.query_with_doc_ids(request.query, doc_ids=request.doc_ids, top_k=request.top_k)
    else:
        docs = await rag.query(request.query, top_k=request.top_k)
    return RAGQueryResponse(
        documents=[{"id":d.id,"content":d.content,"score":round(d.score,4),"source":d.metadata.get("source","unknown")} for d in docs],
        total=len(docs)
    )


@router.post("/rag/upload", response_model=FileUploadResponse)
async def rag_upload(file: UploadFile = File(...), req: Request = None):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename empty")
    doc_id = uuid.uuid4().hex
    fp = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    content_data = await file.read(); fp.write_bytes(content_data)
    try:
        rag = RAGPipeline()
        chunks = await rag.ingest_file(str(fp), metadata={"doc_id": doc_id})
        # Save doc metadata with user scope
        st, sid = _resolve_scope(req) if req else ("none", "")
        from fastapi import Request as _R
        _reload_docs()
        _doc_store[doc_id] = {
            "filename": file.filename,
            "file_path": str(fp),
            "chunks": chunks,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_owner_type": st,
            "_owner_id": sid,
        }
        _save_doc_store(_doc_store)
        return FileUploadResponse(filename=file.filename, chunks=chunks, status="ok", doc_id=doc_id)
    except Exception as e:
        logger.error(f"ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=HistoryResponse)
async def get_history(req: Request, device_id: str | None = Query(None)):
    st, sid = _resolve_scope(req)
    if st == "none" and device_id:
        st, sid = "device", device_id
    _reload(); _migrate_legacy()
    scoped = _get_scoped_conversations(st, sid)
    conversations = []
    for cid, entry in scoped.items():
        msgs = _gm(entry)
        title = _gt(entry, msgs)
        created_at = entry.get("created_at", datetime.now(timezone.utc).isoformat()) if isinstance(entry, dict) else datetime.now(timezone.utc).isoformat()
        conversations.append(HistoryItem(id=cid, title=title, created_at=created_at, message_count=len(msgs)))
    conversations.reverse()
    return HistoryResponse(conversations=conversations)


@router.get("/history/{conversation_id}")
async def get_conversation(conversation_id: str, req: Request):
    st, sid = _resolve_scope(req)
    _reload()
    if conversation_id not in _history_store:
        raise HTTPException(status_code=404, detail="not found")
    entry = _history_store[conversation_id]
    if isinstance(entry, dict):
        ot, oi = entry.get("_owner_type",""), entry.get("_owner_id","")
        if ot and oi and (ot != st or oi != sid):
            raise HTTPException(status_code=404, detail="not found")
        msgs = entry.get("messages", [])
    else:
        msgs = entry if isinstance(entry, list) else []
    return {"conversation_id": conversation_id, "messages": msgs}


@router.put("/history/{conversation_id}/title")
async def rename_history(conversation_id: str, body: dict, req: Request):
    st, sid = _resolve_scope(req)
    _reload()
    if conversation_id not in _history_store:
        raise HTTPException(status_code=404, detail="not found")
    entry = _history_store[conversation_id]
    if isinstance(entry, dict):
        ot, oi = entry.get("_owner_type",""), entry.get("_owner_id","")
        if ot and oi and (ot != st or oi != sid):
            raise HTTPException(status_code=404, detail="not found")
    nt = body.get("title","").strip()
    if not nt:
        raise HTTPException(status_code=422, detail="title empty")
    if isinstance(entry, list):
        _history_store[conversation_id] = {"messages": entry, "title": nt}
    elif isinstance(entry, dict):
        entry["title"] = nt
    _save_history_store(_history_store)
    return {"status": "ok", "title": nt}


@router.delete("/history/{conversation_id}")
async def delete_history(conversation_id: str, req: Request):
    st, sid = _resolve_scope(req)
    _reload()
    if conversation_id not in _history_store:
        raise HTTPException(status_code=404, detail="not found")
    entry = _history_store[conversation_id]
    if isinstance(entry, dict):
        ot, oi = entry.get("_owner_type",""), entry.get("_owner_id","")
        if ot and oi and (ot != st or oi != sid):
            raise HTTPException(status_code=404, detail="not found")
    del _history_store[conversation_id]
    _save_history_store(_history_store)
    return {"status": "ok"}


@router.post("/auth/migrate")
async def migrate_conversations(body: MigrateRequest, req: Request):
    st, sid = _resolve_scope(req)
    if st != "user":
        raise HTTPException(status_code=401, detail="login required")
    if not body.device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    _reload(); _migrate_legacy()
    migrated = 0
    for cid, entry in _history_store.items():
        if isinstance(entry, dict) and entry.get("_owner_type") in ("device", "none") and (entry.get("_owner_id") == body.device_id or entry.get("_owner_type") == "none"):
            entry["_owner_type"] = "user"
            entry["_owner_id"] = sid
            migrated += 1
    if migrated > 0:
        _save_history_store(_history_store)
    logger.info(f"Migrated {migrated} conversations from device {body.device_id} to user {sid}")
    return {"status": "ok", "migrated": migrated}


@router.get("/rag/documents")
async def list_documents(req: Request):
    """List documents for current user/device"""
    st, sid = _resolve_scope(req)
    _reload_docs()
    docs = []
    for did, d in _doc_store.items():
        if d.get("_owner_type") == st and d.get("_owner_id") == sid:
            docs.append({
                "id": did,
                "filename": d["filename"],
                "chunks": d.get("chunks", 0),
                "created_at": d.get("created_at", ""),
                "file_type": d.get("filename", "").rsplit(".", 1)[-1].lower() if d.get("filename") else "",
                "file_path": d.get("file_path", ""),
            })
    # Sort by created_at descending
    docs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"documents": docs, "total": len(docs)}


@router.delete("/rag/documents/{doc_id}")
async def delete_document(doc_id: str, req: Request):
    """Delete a document and its chunks"""
    st, sid = _resolve_scope(req)
    _reload_docs()
    d = _doc_store.get(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="document not found")
    if d.get("_owner_type") != st or d.get("_owner_id") != sid:
        raise HTTPException(status_code=403, detail="permission denied")
    # Remove from ChromaDB
    try:
        rag = RAGPipeline()
        await rag.delete_by_doc_id(doc_id)
    except Exception as e:
        logger.warning(f"Chroma delete failed: {e}")
    # Clean up file
    fp = Path(d["file_path"]) if d.get("file_path") else None
    if fp and fp.exists():
        try:
            fp.unlink()
        except OSError:
            pass
    del _doc_store[doc_id]
    _save_doc_store(_doc_store)
    return {"status": "ok", "deleted": doc_id}


@router.get("/config")
async def get_config():
    settings = get_settings()
    return {
        "model_provider": settings.MODEL_PROVIDER,
        "llm_model": settings.llm.MODEL,
        "embedding_model": settings.embedding.MODEL,
        "rag_enabled": True,
        "rag_document_count": RAGPipeline().document_count,
    }


