# =============================================================
# Agent CUG — Windows 原生部署脚本（无需 Docker）
# =============================================================
# 用法: 右键 "使用 PowerShell 运行" 或:
#   powershell -ExecutionPolicy Bypass -File deploy-windows.ps1
# =============================================================

$ErrorActionPreference = "Continue"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agent CUG — RAG 服务部署 (Windows 原生)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "本脚本将帮你部署三个 RAG 服务：" -ForegroundColor White
Write-Host "  1. Docling    — 文档解析 (本地 pip)" -ForegroundColor Yellow
Write-Host "  2. Qdrant     — 向量数据库 (Cloud 免费层)" -ForegroundColor Yellow
Write-Host "  3. AnythingLLM — RAG 引擎 (Desktop App)" -ForegroundColor Yellow
Write-Host ""

# =========================================================
# Step 1: 安装并启动 Docling Serve
# =========================================================
Write-Host "--- [1/3] Docling Serve ---" -ForegroundColor Cyan

$doclingRunning = $false
try { 
    $null = Invoke-WebRequest -Uri "http://localhost:5001/health" -TimeoutSec 3 -UseBasicParsing
    $doclingRunning = $true
} catch {}

if (-not $doclingRunning) {
    Write-Host "  安装 Docling Serve..."
    pip install docling-serve -q 2>$null
    
    Write-Host "  启动 Docling Serve (首次需下载模型，约 2-5 分钟)..."
    Start-Process -FilePath "python" `
        -ArgumentList "-m", "docling_serve", "serve", "--host", "0.0.0.0", "--port", "5001" `
        -WindowStyle Minimized
    
    Write-Host "  等待 Docling 就绪..."
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 5
        try {
            $null = Invoke-WebRequest -Uri "http://localhost:5001/health" -TimeoutSec 3 -UseBasicParsing
            Write-Host "  ✅ Docling 就绪！http://localhost:5001"
            break
        } catch {
            if ($i % 6 -eq 5) { Write-Host "  仍在加载模型... ($(($i+1)*5)s)" }
        }
    }
} else {
    Write-Host "  ✅ Docling 已在运行"
}

# =========================================================
# Step 2: Qdrant Cloud 配置
# =========================================================
Write-Host ""
Write-Host "--- [2/3] Qdrant Cloud ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Qdrant 无 Windows 原生版本，推荐使用 Qdrant Cloud 免费层。" -ForegroundColor White
Write-Host ""
Write-Host "  请按以下步骤操作：" -ForegroundColor Yellow
Write-Host "  1. 打开 https://cloud.qdrant.io"
Write-Host "  2. 注册账号 (GitHub/Google 登录)"
Write-Host "  3. 创建 Free Tier 集群"
Write-Host "  4. 在 Clusters → 你的集群 → API Key 获取："
Write-Host "     - Cluster URL (如 https://xxx.gcp.cloud.qdrant.io:6333)"
Write-Host "     - API Key"
Write-Host ""

$qdrantUrl = Read-Host "  粘贴 Qdrant URL (回车跳过，稍后手动配置)"
$qdrantKey = Read-Host "  粘贴 Qdrant API Key (回车跳过)"

if ($qdrantUrl -and $qdrantKey) {
    $env:QDRANT_URL = $qdrantUrl
    $env:QDRANT_API_KEY = $qdrantKey
    Write-Host "  ✅ Qdrant 配置已保存"
} else {
    Write-Host "  ⚠️ 跳过 (稍后手动配置)" -ForegroundColor Yellow
}

# =========================================================
# Step 3: AnythingLLM Desktop
# =========================================================
Write-Host ""
Write-Host "--- [3/3] AnythingLLM Desktop ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "  AnythingLLM Desktop 是 Windows 原生应用，自带 RAG 引擎。" -ForegroundColor White
Write-Host ""
Write-Host "  安装步骤：" -ForegroundColor Yellow
Write-Host "  1. 下载安装包: https://anythingllm.com/download"
Write-Host "  2. 安装并启动"
Write-Host "  3. 首次设置向导中配置："
Write-Host "     - LLM 提供商: DeepSeek"
Write-Host "       API Key: 你的 DeepSeek API Key"
Write-Host "     - Embedding 模型: Native → BAAI/bge-m3"
Write-Host "     - 向量数据库: Qdrant"
Write-Host "       URL: $qdrantUrl"
Write-Host "       API Key: $qdrantKey"
Write-Host "  4. 完成后进入 Settings → API Keys → 生成 API Key"
Write-Host "     (这个 Key 用于 Spring Boot 调用 AnythingLLM)"
Write-Host ""

$anythingllmKey = Read-Host "  粘贴 AnythingLLM API Key (回车跳过)"

if ($anythingllmKey) {
    $env:ANYTHINGLLM_API_KEY = $anythingllmKey
    Write-Host "  ✅ AnythingLLM Key 已保存"
}

# =========================================================
# 生成 .env 配置文件
# =========================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  生成环境变量配置" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $scriptDir "backend\.env"

$envContent = @"
# Agent CUG 环境变量配置
# 生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# ===== DeepSeek LLM =====
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# ===== AnythingLLM =====
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=$anythingllmKey

# ===== Docling =====
DOCLING_BASE_URL=http://localhost:5001

# ===== Qdrant (由 AnythingLLM 管理，这里仅作记录) =====
# QDRANT_URL=$qdrantUrl
# QDRANT_API_KEY=$qdrantKey

# ===== JWT Secret =====
JWT_SECRET=agent-cug-jwt-secret-change-in-production-$(Get-Random)
"@

[System.IO.File]::WriteAllText($envFile, $envContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "  配置文件: $envFile"

# =========================================================
# 完成
# =========================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  🎉 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  服务状态:" -ForegroundColor Cyan
Write-Host "    Docling:      http://localhost:5001"
Write-Host "    AnythingLLM:  http://localhost:3001 (需手动安装 Desktop App)"
Write-Host "    Qdrant:       云端 (cloud.qdrant.io)"
Write-Host ""
Write-Host "  启动业务系统:" -ForegroundColor Yellow
Write-Host "    1. 加载环境变量: Get-Content backend\.env | ForEach-Object { if (`$_ -match '^([^#].+?)=(.+)$') { [Environment]::SetEnvironmentVariable(`$matches[1], `$matches[2], 'Process') } }"
Write-Host "    2. 启动后端: cd backend && mvn spring-boot:run"
Write-Host "    3. 启动前端: cd frontend && npm run dev"
Write-Host ""