# ============================================================
# Agent_CUG 阿里云部署助手 (Linux)
# 在阿里云服务器上运行: bash deploy-aliyun.sh
# ============================================================

echo '========================================'
echo ' Agent_CUG 阿里云部署配置'
echo '========================================'

echo ''
echo '[1/3] 创建 .env 配置文件...'

cat > .env << 'ENVEOF'
# Agent_CUG 环境变量（生产环境）
PROJECT_NAME=Agent_CUG
DEBUG=false
LOG_LEVEL=INFO

# 域名（修改为你的实际域名）
DOMAIN_NAME=YOUR_DOMAIN_HERE

# LLM Provider
MODEL_PROVIDER=mimo
LLM_API_KEY=tp-ctzooudzkterojtpiasmapde6xfgbpswt1o5vtclfq14gh2d
LLM_API_BASE=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# Embedding Provider
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
ENVEOF

echo '  .env 文件已创建'

echo ''
echo '[2/3] 安装 Python 依赖...'
pip install -r requirements.txt

echo ''
echo '[3/3] 创建数据目录...'
mkdir -p data/uploads data/chroma

echo ''
echo '========================================'
echo ' 部署配置完成！'
echo '========================================'
echo ''
echo '启动命令:'
echo '  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
echo ''
echo '后台运行:'
echo '  nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &'
