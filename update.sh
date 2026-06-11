#!/bin/bash
# ========================================
# Agent_CUG 一键更新脚本
# 用法: bash update.sh
# ========================================
set -e

cd /root/Agent_CUG

echo "[1/2] git pull..."
git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "  (no remote changes or not a git repo)"

echo "[2/2] 重启服务..."
pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 1
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
sleep 2

echo ""
echo "验证..."
curl -s http://localhost:8000/api/health
echo ""
echo "Done!"
