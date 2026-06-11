#!/bin/bash
set -e
echo "========================================"
echo " Agent_CUG 完整修复脚本"
echo "========================================"

cd /root/Agent_CUG

# 1. 写入 .env
echo ""
echo "[1/4] 写入 .env..."
cat > .env << 'ENVEOF'
PROJECT_NAME=Agent_CUG
DEBUG=false
LOG_LEVEL=INFO
DOMAIN_NAME=YOUR_DOMAIN
MODEL_PROVIDER=mimo
LLM_API_KEY=tp-ctzooudzkterojtpiasmapde6xfgbpswt1o5vtclfq14gh2d
LLM_API_BASE=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=sk-vbnfrxatxyexeysregjqbyxnmewuomsrgjsnqejgvtzwgfel
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION_NAME=agent_cug_docs
SQLITE_DB_PATH=./data/agent_cug.db
MEMORY_SHORT_TERM_MAX=20
MEMORY_LONG_TERM_TTL_DAYS=90
RAG_TOP_K=5
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_RERANK_ENABLED=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ENVEOF
echo "  [OK] .env created"

# 2. Configure Nginx
echo ""
echo "[2/4] Configuring Nginx..."

cat > /etc/nginx/sites-available/agent-cug << 'NGXEOF'
server {
    listen 80;
    server_name _;

    # Agent_CUG API + Frontend
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}

NGXEOF

# Remove default if exists
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/agent-cug /etc/nginx/sites-enabled/agent-cug

nginx -t && systemctl reload nginx
echo "  [OK] Nginx configured"

# 3. Install deps + create dirs
echo ""
echo "[3/4] Installing dependencies..."
pip install -r requirements.txt -q
mkdir -p data/uploads data/chroma
echo "  [OK] Dependencies installed"

# 4. Restart Python service
echo ""
echo "[4/4] Restarting Python service..."
pkill -f "uvicorn app.main" || true
sleep 1
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
sleep 3

# Verify
echo ""
echo "Verifying..."
curl -s http://localhost:8000/api/health && echo ""
curl -s http://localhost/api/health && echo ""

echo ""
echo "========================================"
echo " Fix complete!"
echo "========================================"
