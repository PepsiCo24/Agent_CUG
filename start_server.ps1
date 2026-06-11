# ============================================================
# Agent_CUG 服务器启动脚本
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Agent_CUG 服务器启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "*** .env 文件不存在，从 .env.example 创建 ***" -ForegroundColor Red
    Copy-Item ".env.example" ".env"
    Write-Host "请编辑 .env 填入真实的 API Key 后重新运行" -ForegroundColor Yellow
    exit 1
}

# 检查 Python 虚拟环境
if (Test-Path ".venv/Scripts/python.exe") {
    $Python = ".venv/Scripts/python.exe"
} else {
    $Python = "python"
}

Write-Host "使用 Python: $Python" -ForegroundColor Green

# 创建数据目录
$dirs = @("./data", "./data/uploads", "./data/chroma")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}

Write-Host "启动服务器: http://0.0.0.0:8000" -ForegroundColor Yellow
Write-Host "按 Ctrl+C 停止" -ForegroundColor Yellow
Write-Host ""

& $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
