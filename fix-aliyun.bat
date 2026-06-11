@echo off
chcp 65001 >nul
echo ========================================
echo  Agent_CUG 阿里云部署修复
echo ========================================
echo.
echo 此脚本将上传 .env 文件到阿里云服务器并重启服务
echo.

set SERVER=47.120.67.70
set USER=root

echo [1/3] 上传 .env 到服务器...
scp .env %USER%@%SERVER%:/root/Agent_CUG/.env
if %ERRORLEVEL% neq 0 (
    echo 上传失败！请检查 SSH 密码是否正确。
    pause
    exit /b 1
)

echo.
echo [2/3] 上传部署脚本...
scp setup-env.sh %USER%@%SERVER%:/root/Agent_CUG/
scp agent-cug.service %USER%@%SERVER%:/root/Agent_CUG/

echo.
echo [3/3] 远程重启服务...
ssh %USER%@%SERVER% "cd /root/Agent_CUG && pkill -f uvicorn; sleep 1; nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 & sleep 2 && curl -s http://localhost:8000/api/health"

echo.
echo ========================================
echo  部署完成！请用浏览器访问你的域名测试。
echo ========================================
pause
