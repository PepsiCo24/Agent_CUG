# =============================================================
# Agent CUG — RAG 基础设施一键部署脚本
# 用法: 右键 → "使用 PowerShell 运行" 或在终端执行:
#   powershell -ExecutionPolicy Bypass -File deploy.ps1
# =============================================================

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$COMPOSE_DIR = "$SCRIPT_DIR\docker"
$COMPOSE_FILE = "$COMPOSE_DIR\docker-compose.yml"
$ENV_FILE = "$COMPOSE_DIR\anythingllm.env"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agent CUG — RAG 基础设施部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===== 1. 检查 Docker =====
Write-Host "[1/5] 检查 Docker 环境..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 未检测到 Docker，请先安装 Docker Desktop" -ForegroundColor Red
    Write-Host "   下载地址: https://www.docker.com/products/docker-desktop/"
    exit 1
}
Write-Host "  ✅ $dockerVersion"

# 检查 Docker 引擎是否运行
$dockerPs = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 引擎未运行，正在启动 Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
    Write-Host "   等待 Docker 引擎启动（最长 120 秒）..."
    for ($i = 0; $i -lt 24; $i++) {
        Start-Sleep -Seconds 5
        docker ps 2>$null
        if ($LASTEXITCODE -eq 0) { break }
        Write-Host -NoNewline "."
    }
    Write-Host ""
    docker ps 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker 引擎启动失败，请手动打开 Docker Desktop 后重试" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  ✅ Docker 引擎运行中"

# ===== 2. 配置 API Key =====
Write-Host ""
Write-Host "[2/5] 配置 API 密钥..." -ForegroundColor Yellow

# 读取现有 .env
$envContent = Get-Content $ENV_FILE -Raw -Encoding UTF8

# DeepSeek API Key
$currentDsKey = [regex]::Match($envContent, 'DeepSeekApiKey=(.+)').Groups[1].Value.Trim()
if ($currentDsKey -eq "sk-your-deepseek-api-key-here" -or [string]::IsNullOrEmpty($currentDsKey)) {
    Write-Host "  请输入 DeepSeek API Key (在 https://platform.deepseek.com 获取):" -ForegroundColor White
    $dsKey = Read-Host "  > "
    if (-not [string]::IsNullOrEmpty($dsKey)) {
        $envContent = $envContent -replace 'DeepSeekApiKey=.+', "DeepSeekApiKey=$dsKey"
        Write-Host "  ✅ DeepSeek API Key 已配置"
    } else {
        Write-Host "  ⚠️ 跳过（可稍后手动编辑 anythingllm.env）" -ForegroundColor Yellow
    }
}

# AnythingLLM Auth Token
Write-Host "  请输入 AnythingLLM API Token (自定义，用于 Spring Boot 调用):" -ForegroundColor White
Write-Host "  默认: agentcug-api-token-change-me" -ForegroundColor Gray
$token = Read-Host "  > "
if (-not [string]::IsNullOrEmpty($token)) {
    $envContent = $envContent -replace 'AUTH_TOKEN=.+', "AUTH_TOKEN=$token"
    Write-Host "  ✅ API Token 已配置"
} else {
    Write-Host "  ⚠️ 使用默认 Token" -ForegroundColor Yellow
}

[System.IO.File]::WriteAllText($ENV_FILE, $envContent, [System.Text.UTF8Encoding]::new($false))

# ===== 3. 拉取镜像 =====
Write-Host ""
Write-Host "[3/5] 拉取 Docker 镜像..." -ForegroundColor Yellow
Push-Location $COMPOSE_DIR
docker compose pull 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 镜像拉取失败" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  ✅ 镜像拉取完成"

# ===== 4. 启动服务 =====
Write-Host ""
Write-Host "[4/5] 启动服务..." -ForegroundColor Yellow
docker compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 服务启动失败" -ForegroundColor Red
    Pop-Location
    exit 1
}

# ===== 5. 等待服务就绪 =====
Write-Host ""
Write-Host "[5/5] 等待服务就绪..." -ForegroundColor Yellow

Write-Host "  等待 Qdrant..."
for ($i = 0; $i -lt 30; $i++) {
    try { 
        $null = Invoke-WebRequest -Uri "http://localhost:6333/health" -TimeoutSec 2 -UseBasicParsing
        Write-Host "  ✅ Qdrant 就绪 (http://localhost:6333)"
        break
    } catch { Start-Sleep -Seconds 2 }
}

Write-Host "  等待 Docling (首次启动需下载模型，可能较久)..."
for ($i = 0; $i -lt 60; $i++) {
    try { 
        $null = Invoke-WebRequest -Uri "http://localhost:5001/health" -TimeoutSec 3 -UseBasicParsing
        Write-Host "  ✅ Docling 就绪 (http://localhost:5001)"
        break
    } catch { 
        if ($i % 5 -eq 0) { Write-Host "  仍在加载模型... ($($i*2)s)" }
        Start-Sleep -Seconds 2 
    }
}

Write-Host "  等待 AnythingLLM..."
for ($i = 0; $i -lt 30; $i++) {
    try { 
        $null = Invoke-WebRequest -Uri "http://localhost:3001/api/ping" -TimeoutSec 3 -UseBasicParsing
        Write-Host "  ✅ AnythingLLM 就绪 (http://localhost:3001)"
        break
    } catch { Start-Sleep -Seconds 2 }
}

Pop-Location

# ===== 完成 =====
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  🎉 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  服务地址:" -ForegroundColor Cyan
Write-Host "    Qdrant:       http://localhost:6333"
Write-Host "    Docling:      http://localhost:5001"
Write-Host "    AnythingLLM:  http://localhost:3001"
Write-Host ""
Write-Host "  ⚠️ 首次使用 AnythingLLM 请访问 http://localhost:3001" -ForegroundColor Yellow
Write-Host "    完成引导设置（选择 DeepSeek + bge-m3 + Qdrant）"
Write-Host ""
Write-Host "  启动业务系统:" -ForegroundColor Cyan
Write-Host "    后端: cd backend && mvn spring-boot:run"
Write-Host "    前端: cd frontend && npm run dev"
Write-Host ""
Write-Host "  停止服务: cd docker && docker compose down" -ForegroundColor Gray