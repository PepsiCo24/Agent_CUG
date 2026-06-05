"""
Agent_CUG FastAPI 应用入口
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import router
from config import get_settings
from core.exceptions import AgentCUGError

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """配置日志系统"""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    setup_logging()
    logger.info("Agent_CUG v1.0.0 启动中...")
    logger.info("LLM Provider: %s", get_settings().MODEL_PROVIDER)
    logger.info("LLM Model: %s", get_settings().llm.MODEL)
    yield
    logger.info("Agent_CUG 关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Agent Operating System — Level 2 Agent",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 全局异常处理 ----

    @app.exception_handler(AgentCUGError)
    async def agent_error_handler(request: Request, exc: AgentCUGError) -> JSONResponse:
        logger.error("AgentCUGError [%s]: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error": exc.code,
                "detail": exc.message,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("ValueError: %s", exc)
        return JSONResponse(
            status_code=400,
            content={
                "error": "VALIDATION_ERROR",
                "detail": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "服务器内部错误" if not settings.DEBUG else str(exc),
            },
        )

    # API 路由
    app.include_router(router)

    # 静态文件（前端）
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()