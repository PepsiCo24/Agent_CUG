# ============================================================
# Agent_CUG 一键部署到阿里云
# 用法: .\deploy-to-aliyun.ps1
# ============================================================

param(
    [string]$ServerIP = "47.120.67.70",
    [string]$User = "root",
    [string]$RemotePath = "/root/Agent_CUG"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Agent_CUG 阿里云一键部署" -ForegroundColor Cyan
Write-Host " 目标: ${User}@${ServerIP}:${RemotePath}" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Upload .env
Write-Host "`n[1/4] 上传 .env 配置文件..." -ForegroundColor Yellow
scp .env ${User}@${ServerIP}:${RemotePath}/.env
Write-Host "  .env 上传完成" -ForegroundColor Green

# Step 2: Upload setup script
Write-Host "`n[2/4] 上传部署脚本..." -ForegroundColor Yellow
scp setup-env.sh agent-cug.service ${User}@${ServerIP}:${RemotePath}/
Write-Host "  脚本上传完成" -ForegroundColor Green

# Step 3: Run setup on remote
Write-Host "`n[3/4] 远程安装依赖..." -ForegroundColor Yellow
ssh ${User}@${ServerIP} "cd ${RemotePath} && pip install -r requirements.txt -q && mkdir -p data/uploads data/chroma"
Write-Host "  依赖安装完成" -ForegroundColor Green

# Step 4: Restart service
Write-Host "`n[4/4] 重启服务..." -ForegroundColor Yellow
ssh ${User}@${ServerIP} "cd ${RemotePath} && pkill -f uvicorn || true; nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 & sleep 2"
Write-Host "  服务已重启" -ForegroundColor Green

# Verify
Write-Host "`n验证部署..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
try {
    $r = Invoke-WebRequest -Uri "http://${ServerIP}:8000/api/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "  [OK] 服务器响应: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] 无法直接访问，请用域名测试" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " 部署完成!" -ForegroundColor Green
Write-Host " 访问: http://${ServerIP}:8000" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
