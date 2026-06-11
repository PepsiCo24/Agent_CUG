# Agent_CUG — 智能 AI 助手

> 基于 LangGraph + ReAct 的 Agent 操作系统，支持多模型、RAG、工具调用、记忆系统

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-61%20passed-brightgreen)]()
[![GitHub](https://img.shields.io/badge/GitHub-PepsiCo24%2FAgent__CUG-black?logo=github)](https://github.com/PepsiCo24/Agent_CUG)

---

## 功能特性

### 核心能力

| 功能 | 说明 |
|------|------|
| 智能对话 | 支持流式 (SSE) 和非流式聊天，Markdown 富文本渲染 |
| RAG 检索增强 | 文档上传 → 智能分块 → 向量检索 → 重排序 → LLM 回答 |
| 工具调用 | 计算器、时间查询、知识库检索、网络搜索 |
| 记忆系统 | 短期记忆 (SQLite) + 长期记忆 (Chroma)，自动去重与过期清理 |
| 多模型支持 | Mimo / OpenAI / DeepSeek / Qwen / Claude，统一接口即插即用 |
| 思考过程 | 复杂问题自动展示推理链，可折叠查看 |

### 技术架构

```
Web UI (SPA)  ←→  FastAPI Backend  ←→  LangGraph Agent
                      ↕                    ↕
                 SSE Streaming        ReAct Workflow
                      ↕                    ↕
              ┌───────┴────────┬───────────┴──────────┐
              │    RAG         │    Memory   │  Tools  │
              │ Chroma + Rank  │ SQLite+Chroma│ Calc   │
              └────────────────┴─────────────┴─────────┘
```

---

## 快速开始

### 环境要求

- Python 3.12+
- Git

### 安装

```bash
# 克隆项目
git clone https://github.com/PepsiCo24/Agent_CUG.git
cd Agent_CUG

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制环境变量模板
copy .env.example .env     # Windows
# cp .env.example .env      # Linux/Mac

# 编辑 .env，填入 API Key
# LLM_API_KEY=your_key_here
# EMBEDDING_API_KEY=your_key_here
```

### 启动

```bash
# 开发模式（热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 **http://localhost:8000** 即可使用。

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 + 文档数量 |
| `GET` | `/api/config` | 系统配置 |
| `POST` | `/api/chat` | 同步聊天 |
| `POST` | `/api/chat/stream` | SSE 流式聊天 |
| `POST` | `/api/rag/query` | RAG 文档检索 |
| `POST` | `/api/rag/upload` | 上传文档到知识库 |
| `GET` | `/api/history` | 对话历史列表 |
| `GET` | `/api/history/{id}` | 对话详情 |
| `PUT` | `/api/history/{id}/title` | 重命名对话 |
| `DELETE` | `/api/history/{id}` | 删除对话 |
| `GET` | `/` | Web UI 前端 |

---

## 项目结构

```
Agent_CUG/
├── app/            # FastAPI 入口 + 生命周期管理
├── api/            # API 路由 + Pydantic Schema
├── agent/          # LangGraph 工作流 (Router → RAG → Tools → LLM)
├── rag/            # RAG 流水线 (加载 → 分块 → 检索 → 重排序)
├── memory/         # 记忆系统 (SQLite 短期 + Chroma 长期)
├── tools/          # 工具注册表 (计算器、时间、搜索、知识库)
├── llm/            # LLM 适配器 (Mimo/OpenAI/DeepSeek/Qwen/Claude)
├── embedding/      # Embedding 适配器 (SiliconFlow/OpenAI)
├── prompt/         # Prompt 模板集中管理
├── core/           # 抽象基类 (SOLID 原则)
├── config/         # Pydantic Settings 配置管理
├── frontend/       # Web UI (ChatGPT 风格)
├── tests/          # 测试 (61 个用例)
├── .env.example    # 环境变量模板
└── requirements.txt
```

---

## 设计原则

- **Clean Architecture** — 分层解耦，依赖倒置
- **SOLID** — 面向接口编程，工厂模式注入
- **安全第一** — API Key 仅通过环境变量，禁止硬编码
- **单例模式** — ChromaDB / RAGPipeline / MemoryManager 共享连接池

---

## 更新日志

### v1.1.0 (2026-06)

- LLM 调用自动重试机制（指数退避）
- ChromaDB / RAGPipeline 全局单例
- 历史记录 JSON 持久化
- 前端：删除/重命名对话、暗色模式、Ctrl+Enter 快捷键
- 配置验证 + 优雅关闭
- 文本排版智能修复（数字空格、中英文间距）
- 61 项自动化测试覆盖

---

## License

MIT © 2026 Agent_CUG
