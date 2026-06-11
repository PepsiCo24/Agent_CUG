#!/bin/bash
# ============================================================
# Agent_CUG 阿里云环境配置 (在服务器上运行此脚本)
# 解决 "Missing credentials" 错误
# ============================================================

set -e

echo "========================================"
echo " Agent_CUG 阿里云环境配置"
echo "========================================"

cd "$(dirname "$0")"

# 1. 写入 .env 文件（包含真实 API Key）
echo ""
echo "[1/4] 写入 .env 配置文件..."

cat > .env << 'EOF'
# Agent_CUG 生产环境变量
PROJECT_NAME=Agent_CUG
DEBUG=false
LOG_LEVEL=INFO

# 域名
DOMAIN_NAME=YOUR_DOMAIN_HERE

# LLM Provider - Mimo
MODEL_PROVIDER=mimo
LLM_API_KEY=tp-ctzooudzkterojtpiasmapde6xfgbpswt1o5vtclfq14gh2d
LLM_API_BASE=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# Embedding Provider - SiliconFlow
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=sk-vbnfrxatxyexeysregjqbyxnmewuomsrgjsnqejgvtzwgfel
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3

# Chroma
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION_NAME=agent_cug_docs

# SQLite
SQLITE_DB_PATH=./data/agent_cug.db

# Memory
MEMORY_SHORT_TERM_MAX=20
MEMORY_LONG_TERM_TTL_DAYS=90

# RAG
RAG_TOP_K=5
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_RERANK_ENABLED=true

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
EOF

echo "  [OK] .env 文件已创建"

# 2. 安装 Python 依赖
echo ""
echo "[2/4] 安装 Python 依赖..."
pip install -r requirements.txt -q
echo "  [OK] 依赖安装完成"

# 3. 创建数据目录
echo ""
echo "[3/4] 创建数据目录..."
mkdir -p data/uploads data/chroma
echo "  [OK] 数据目录已创建"

# 4. 验证配置
echo ""
echo "[4/4] 验证配置..."
python3 -c "
from config import get_settings
s = get_settings()
assert len(s.llm.API_KEY) > 10, 'LLM API Key 无效!'
print(f'  Provider: {s.MODEL_PROVIDER}')
print(f'  Model: {s.llm.MODEL}')
print(f'  API Base: {s.llm.API_BASE}')
print(f'  Embedding: {s.embedding.MODEL}')
print('  [OK] 所有配置验证通过!')
"

echo ""
echo "========================================"
echo " 配置完成!"
echo "========================================"
echo ""
echo "启动服务:"
echo "  python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "后台运行:"
echo "  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &"
echo ""
echo "使用 systemd (推荐):"
echo "  sudo cp agent-cug.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable agent-cug"
echo "  sudo systemctl start agent-cug"
