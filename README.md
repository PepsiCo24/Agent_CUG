# Agent_CUG — Agent Operating System

> 🚀 个人研发 + 科研学习 + 企业级扩展的 Agent 操作系统

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-PepsiCo24/Agent__CUG-black)](https://github.com/PepsiCo24/Agent_CUG)

---

## 📋 项目概述

Agent_CUG 是一个可持续演进的 **Agent Operating System**，从 Level 2 Agent 起步，逐步演进为支持 GraphRAG、Multi-Agent、Workflow Engine 等高级特性的完整 Agent 平台。

### 当前阶段：Level 2 Agent

| 模块 | 状态 | 说明 |
|------|------|------|
| Chat Agent | ✅ | 基于 LangGraph + ReAct |
| RAG | ✅ | 文档加载 → 分块 → Chroma → 检索 → 重排序 |
| Memory | ✅ | 短期记忆(SQLite) + 长期记忆(Chroma) |
| Tool Calling | ✅ | 统一工具接口(计算器、时间) |
| ReAct | ✅ | Reasoning + Acting 工作流 |
| LangGraph | ✅ | 状态图编排 |
| FastAPI | ✅ | RESTful API + SSE 流式 |
| Web UI | ✅ | SPA + 原生JS + ChatGPT 风格 |

---

## 🏗️ 架构

`
┌──────────────────────────────────────────────┐
│                  Web UI (SPA)                 │
│              SSE Streaming Chat              │
├──────────────────────────────────────────────┤
│                FastAPI Backend                │
├──────────┬──────────┬──────────┬─────────────┤
│  Agent   │   RAG    │  Memory  │    Tools    │
│ LangGraph│ Chroma   │  SQLite  │ Calculator  │
│  ReAct   │ Retriever│  Chroma  │    Time     │
├──────────┴──────────┴──────────┴─────────────┤
│           LLM Adapter / Embedding Adapter     │
│       Mimo · OpenAI · DeepSeek · Qwen        │
└──────────────────────────────────────────────┘
`

---

## 🚀 快速开始

### 1. 环境准备

`ash
# Python 3.12+
python --version

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
`

### 2. 配置环境变量

`ash
# 复制配置模板
copy .env.example .env   # Windows
# cp .env.example .env    # Linux/Mac

# 编辑 .env 填入真实 API Key
`

### 3. 启动服务

`ash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
`

### 4. 访问

打开浏览器访问 http://localhost:8000

---

## 📁 项目结构

`
Agent_CUG/
├── app/            # FastAPI 应用入口
│   └── main.py
├── api/            # API 路由 & Schema
│   ├── routes.py
│   └── schemas.py
├── agent/          # Agent 工作流
│   ├── state.py    # LangGraph State
│   └── __init__.py # ReAct Workflow
├── rag/            # RAG 流水线
│   ├── loaders.py  # PDF/DOCX/TXT/MD
│   ├── chunker.py
│   ├── retriever.py
│   └── reranker.py
├── memory/         # 记忆系统
│   └── __init__.py # SQLite + Chroma
├── tools/          # 工具框架
│   └── __init__.py # Calculator, Time
├── llm/            # LLM Adapter
│   └── __init__.py
├── embedding/      # Embedding Adapter
│   └── __init__.py
├── prompt/         # Prompt 模板
│   └── __init__.py
├── core/           # 抽象基类
│   └── base.py
├── config/         # 配置管理
│   └── settings.py
├── frontend/       # Web UI
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/          # 测试
├── docs/           # 文档
├── .env.example    # 环境变量模板
├── .gitignore
├── requirements.txt
└── README.md
`

---

## 🔧 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| POST | /api/chat | 同步聊天 |
| POST | /api/chat/stream | SSE 流式聊天 |
| POST | /api/rag/query | RAG 检索 |
| POST | /api/rag/upload | 文件上传到知识库 |
| GET | /api/history | 对话历史 |
| GET | /api/config | 系统配置 |
| GET | / | Web UI |

---

## 🎯 设计原则

- **Clean Architecture** — 分层解耦
- **SOLID** — 依赖抽象而非具体实现
- **DDD** — 领域驱动设计
- **Dependency Injection** — 工厂模式
- **安全第一** — API Key 仅通过环境变量

---

## 📝 License

MIT © 2026 Agent_CUG


## 更新日志

### v1.1.0 (2026-06)
- LLM 调用增加自动重试机制
- ChromaDB 全局单例模式，避免重复创建客户端
- RAGPipeline 单例模式
- MemoryManager 共享 Chroma 连接
- 历史记录持久化到 JSON 文件
- 前端增强：删除/重命名对话、自动滚动、暗色模式检测、Ctrl+Enter 快捷键
- 优雅关闭机制
- 配置验证
- 会话导出 API
- 工具使用统计
- 更多单元测试和集成测试覆盖
