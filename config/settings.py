"""
Agent_CUG 统一配置管理
基于 Pydantic V2 Settings，从环境变量加载所有配置
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    API_KEY: str = ""
    API_BASE: str = "https://api.openai.com/v1"
    MODEL: str = "gpt-4o"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", env_file=".env", extra="ignore")

    API_KEY: str = ""
    API_BASE: str = "https://api.openai.com/v1"
    MODEL: str = "text-embedding-3-small"


class ChromaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHROMA_", env_file=".env", extra="ignore")

    PERSIST_DIR: str = "./data/chroma"
    COLLECTION_NAME: str = "agent_cug_docs"


class SQLiteSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQLITE_", env_file=".env", extra="ignore")

    DB_PATH: str = "./data/agent_cug.db"


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORY_", env_file=".env", extra="ignore")

    SHORT_TERM_MAX: int = 20
    LONG_TERM_TTL_DAYS: int = 90


class RAGSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    TOP_K: int = 5
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    RERANK_ENABLED: bool = True


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVER_", env_file=".env", extra="ignore")

    HOST: str = "0.0.0.0"
    PORT: int = 8000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 项目基础
    PROJECT_NAME: str = "Agent_CUG"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # 域名（部署时修改环境变量 DOMAIN_NAME）
    DOMAIN_NAME: str = "localhost"

    # LLM Provider（支持: mimo, openai, deepseek, qwen, claude）
    MODEL_PROVIDER: Literal["mimo", "openai", "deepseek", "qwen", "claude"] = "mimo"

    # Embedding Provider
    EMBEDDING_PROVIDER: Literal["siliconflow", "openai"] = "siliconflow"

    @property
    def llm(self) -> LLMSettings:
        return LLMSettings()

    @property
    def embedding(self) -> EmbeddingSettings:
        return EmbeddingSettings()

    @property
    def chroma(self) -> ChromaSettings:
        return ChromaSettings()

    @property
    def sqlite(self) -> SQLiteSettings:
        return SQLiteSettings()

    @property
    def memory(self) -> MemorySettings:
        return MemorySettings()

    @property
    def rag(self) -> RAGSettings:
        return RAGSettings()

    @property
    def server(self) -> ServerSettings:
        return ServerSettings()

    def resolve_path(self, relative_path: str) -> Path:
        """将相对路径解析为基于项目根目录的绝对路径"""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
