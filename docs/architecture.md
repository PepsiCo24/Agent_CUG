# Agent_CUG 架构设计文档

## 1. 概述

Agent_CUG 是一个可持续演进的 Agent Operating System，采用 Clean Architecture + SOLID + DDD 设计原则。

### 1.1 当前阶段：Level 2 Agent

- Chat Agent（LangGraph + ReAct）
- RAG（Chroma 向量检索）
- Memory（SQLite 短期 + Chroma 长期）
- Tool Calling（统一工具接口）
- FastAPI Backend + Web UI

### 1.2 未来演进

GraphRAG → Multi-Agent → Workflow Engine → Knowledge Graph → Sandbox → Multimodal

---

## 2. 架构分层

```
┌──────────────────────────────────────────────────┐
│                Presentation Layer                 │
│         Web UI (SPA)  |  FastAPI Routes          │
├──────────────────────────────────────────────────┤
│              Application Layer                    │
│       Agent Workflow (LangGraph + ReAct)          │
├──────────┬──────────┬──────────┬─────────────────┤
│  Domain  │   RAG    │  Memory  │     Tools       │
│  Layer   │ Pipeline │  Manager │   Registry      │
├──────────┴──────────┴──────────┴─────────────────┤
│           Infrastructure Layer                    │
│   LLM Adapter  |  Embedding Adapter              │
│   Chroma   |  SQLite  |  OpenAI API              │
└──────────────────────────────────────────────────┘
```

---

## 3. 核心模块

### 3.1 LLM Adapter (`llm/`)

统一 LLM 接口，支持多 Provider 切换：

| Provider | Model | API Base |
|----------|-------|----------|
| mimo | mimo-v2.5-pro | token-plan-cn.xiaomimimo.com |
| openai | gpt-4o | api.openai.com |
| deepseek | deepseek-chat | api.deepseek.com |
| qwen | qwen-plus | dashscope.aliyuncs.com |
| claude | claude-3-5-sonnet | api.anthropic.com |

切换方式：修改 `.env` 中的 `MODEL_PROVIDER`

### 3.2 Embedding Adapter (`embedding/`)

| Provider | Model | Dimensions |
|----------|-------|------------|
| siliconflow | BAAI/bge-m3 | 1024 |
| openai | text-embedding-3-small | 1536 |

### 3.3 RAG Pipeline (`rag/`)

```
Document Loader → TextChunker → Embedding → Chroma → Retriever → Reranker
     │               │             │          │          │           │
  PDF/DOCX      512 chars     BGE-M3     Cosine      Top-K     Keyword
  TXT/MD        50 overlap               Search      retrieval   boost
```

### 3.4 Memory System (`memory/`)

- **短期记忆**：SQLite，最近 N 条消息（FIFO）
- **长期记忆**：Chroma 向量检索 + SQLite 元数据
- **操作**：写入 / 检索 / 评分 / 去重 / TTL 清理

### 3.5 Tool Framework (`tools/`)

| Tool | Name | Description |
|------|------|-------------|
| TimeTool | get_current_time | 获取当前时间 |
| CalculatorTool | calculate | 安全数学计算 |
| RAGTool | search_knowledge_base | 知识库检索 |
| SearchTool | web_search | DuckDuckGo 网络搜索 |

### 3.6 Agent Workflow (`agent/`)

```
User Input
    ↓
Router (意图分析)
    ↓
Memory Retrieval (长期记忆 + 近期对话)
    ↓
RAG Retrieval (向量检索 + 重排序)    Tool Planning → Tool Execution
    ↓                                       ↓
Prompt Builder ←────────────────────────────┘
    ↓
LLM Generate (流式输出)
    ↓
Final Answer → Memory Save
```

State 字段：user_input, chat_history, retrieved_docs, retrieved_memory, tool_calls, observations, final_answer

---

## 4. API 端点

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | 健康检查 |
| GET | /api/config | 系统配置 |
| POST | /api/chat | 同步聊天 |
| POST | /api/chat/stream | SSE 流式聊天 |
| POST | /api/rag/query | RAG 检索 |
| POST | /api/rag/upload | 文件上传 |
| GET | /api/history | 对话历史 |
| DELETE | /api/history/{id} | 删除历史 |
| GET | / | Web UI |

---

## 5. 配置管理

所有配置通过 Pydantic V2 Settings 从环境变量读取：

- 敏感信息（API Key）仅通过环境变量
- `.env.example` 提供配置模板
- `DOMAIN_NAME` 支持随时更换域名
- `MODEL_PROVIDER` 支持 Provider 切换

---

## 6. 设计原则

- **Clean Architecture**：分层解耦，依赖方向向内
- **SOLID**：单一职责、开闭原则、依赖倒置
- **DDD**：领域模型驱动设计
- **DI**：工厂模式创建实例
- **No God Class**：每个模块职责单一
- **No Circular Deps**：单向依赖，无循环引用

---

## 7. 部署

目标环境：Alibaba Cloud ECS

```bash
# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 使用 Gunicorn（生产）
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## 8. 测试

```bash
# 运行全部测试
pytest tests/ -v

# 覆盖率
pytest tests/ --cov=. --cov-report=html
```