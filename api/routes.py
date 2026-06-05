"""
API Routes — FastAPI 路由
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from agent import get_agent
from api.schemas import (
    ChatRequest,
    ChatResponse,
    FileUploadResponse,
    HealthResponse,
    HistoryItem,
    HistoryResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from config import get_settings
from rag import RAGPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# 简单的内存历史存储（生产环境应使用 SQLite）
_history_store: dict[str, list[dict]] = {}

# 上传目录
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    rag = RAGPipeline()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        document_count=rag.document_count,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口（同步）"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="消息不能为空")

    agent = get_agent()
    conversation_id = request.conversation_id or str(uuid.uuid4())

    try:
        result = await agent.run(request.message, conversation_id)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

    # 保存到历史存储
    if conversation_id not in _history_store:
        _history_store[conversation_id] = []
    _history_store[conversation_id].append({"role": "user", "content": request.message})
    _history_store[conversation_id].append({"role": "assistant", "content": result.get("final_answer", "")})

    # 添加来源信息
    sources: list[dict[str, str]] = []
    if result.get("retrieved_docs"):
        for doc in result["retrieved_docs"]:
            sources.append({
                "source": doc.metadata.get("source", "未知"),
                "content": doc.content[:200],
            })

    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.get("final_answer", ""),
        sources=sources,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """聊天接口（流式 SSE）"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="消息不能为空")

    agent = get_agent()
    conversation_id = request.conversation_id or str(uuid.uuid4())

    async def event_generator():
        full_answer = ""
        try:
            if conversation_id not in _history_store:
                _history_store[conversation_id] = []
            _history_store[conversation_id].append({"role": "user", "content": request.message})

            async for token in agent.run_stream(request.message, conversation_id):
                full_answer += token
                yield {"event": "token", "data": token}

            _history_store[conversation_id].append({"role": "assistant", "content": full_answer})

            yield {"event": "done", "data": json.dumps({
                "conversation_id": conversation_id,
                "full_answer": full_answer,
            })}
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """RAG 查询（仅检索，不含 LLM）"""
    rag = RAGPipeline()
    docs = await rag.query(request.query, top_k=request.top_k)

    return RAGQueryResponse(
        documents=[
            {
                "id": doc.id,
                "content": doc.content,
                "score": round(doc.score, 4),
                "source": doc.metadata.get("source", "未知"),
            }
            for doc in docs
        ],
        total=len(docs),
    )


@router.post("/rag/upload", response_model=FileUploadResponse)
async def rag_upload(file: UploadFile = File(...)):
    """上传文件到 RAG 知识库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 保存文件
    file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    file_path.write_bytes(content)

    try:
        rag = RAGPipeline()
        chunks = await rag.ingest_file(str(file_path))

        return FileUploadResponse(
            filename=file.filename,
            chunks=chunks,
            status="ok",
        )
    except Exception as e:
        logger.error(f"文件摄入失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """获取对话历史"""
    conversations: list[HistoryItem] = []

    if _history_store:
        for conv_id, messages in _history_store.items():
            title = "新对话"
            if messages:
                first_msg = messages[0]
                title = first_msg.get("content", "新对话")[:30]
            conversations.append(HistoryItem(
                id=conv_id,
                title=title,
                created_at=datetime.now(timezone.utc).isoformat(),
                message_count=len(messages),
            ))

    return HistoryResponse(conversations=conversations)


@router.delete("/history/{conversation_id}")
async def delete_history(conversation_id: str):
    """删除对话历史"""
    if conversation_id in _history_store:
        del _history_store[conversation_id]
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/config")
async def get_config():
    """获取前端配置"""
    settings = get_settings()
    return {
        "model_provider": settings.MODEL_PROVIDER,
        "llm_model": settings.llm.MODEL,
        "embedding_model": settings.embedding.MODEL,
        "rag_enabled": True,
        "rag_document_count": RAGPipeline().document_count,
    }