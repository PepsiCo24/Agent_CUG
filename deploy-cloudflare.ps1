# ============================================
# Agent_CUG Cloudflare ???????
# ??: cug-agent.click
# ??: ?????? Cloudflare ? NS ???
# ??: .\deploy-cloudflare.ps1
# ============================================

$ErrorActionPreference = "Stop"
$Domain = "cug-agent.click"
$TunnelName = "cug-agent"
$Cloudflared = "C:\cloudflared\cloudflared.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Agent_CUG Cloudflare ??" -ForegroundColor Cyan
Write-Host " ??: $Domain" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---- Step 1: Cloudflare ?? ----
Write-Host "`n[1/6] Cloudflare ?? (?????)..." -ForegroundColor Yellow
& $Cloudflared tunnel login

# ---- Step 2: ?? Tunnel ----
Write-Host "`n[2/6] ?? Cloudflare Tunnel..." -ForegroundColor Yellow
& $Cloudflared tunnel create $TunnelName 2>&1 | ForEach-Object { Write-Host $_ }

# ---- Step 3: DNS ?? ----
Write-Host "`n[3/6] ?? DNS ??..." -ForegroundColor Yellow
& $Cloudflared tunnel route dns $TunnelName "api.$Domain"
& $Cloudflared tunnel route dns $TunnelName "www.$Domain"
Write-Host "  api.$Domain -> Tunnel"
Write-Host "  www.$Domain -> Tunnel"

# ---- Step 4: ?? config.yml ----
Write-Host "`n[4/6] ?? Tunnel ??..." -ForegroundColor Yellow
$ConfigDir = "$env:USERPROFILE\.cloudflared"
$TunnelId = (Get-ChildItem "$ConfigDir\*.json" | Where-Object { $_.Name -match '^[a-f0-9-]+\.json$' } | Select-Object -First 1).BaseName

$ConfigLines = @(
    "tunnel: $TunnelId",
    "credentials-file: $ConfigDir\$TunnelId.json",
    "",
    "ingress:",
    "  - hostname: api.$Domain",
    "    service: http://localhost:8000",
    "  - hostname: www.$Domain",
    "    service: http://localhost:8000",
    "  - hostname: $Domain",
    "    service: http://localhost:8000",
    "  - service: http_status:404"
)
$ConfigLines | Out-File -FilePath "$ConfigDir\config.yml" -Encoding UTF8
Write-Host "  ????? $ConfigDir\config.yml"

# ---- Step 5: ?? Tunnel ?? ----
Write-Host "`n[5/6] ?? Windows ?? (??????)..." -ForegroundColor Yellow
& $Cloudflared service install
Start-Sleep 3
& $Cloudflared service start

# ---- Step 6: ?? ----
Write-Host "`n[6/6] ????..." -ForegroundColor Yellow
Start-Sleep 3
& $Cloudflared service status

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " ????!" -ForegroundColor Green
Write-Host " ??API: https://api.$Domain" -ForegroundColor Yellow
Write-Host " ??: https://$Domain (??? Cloudflare Pages)" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "??Agent_CUG??: cd E:\Agent_rec\Agent_CUG ; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
