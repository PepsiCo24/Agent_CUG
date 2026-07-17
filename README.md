# Agent CUG

面向个人知识库的 RAG（检索增强生成）应用。用户可以创建知识库、上传 PDF / DOCX / TXT / Markdown 文档，并在文档范围内进行带引用的问答。

项目由 Vue 3 前端、Spring Boot 业务后端和 Python RAG 网关组成；向量数据通过嵌入模型生成后保存在本地 Qdrant 存储中。

## 功能

- 用户注册、登录与 JWT 鉴权
- 知识库的创建、编辑、删除与检索
- PDF、DOCX、TXT、Markdown 文档上传、解析与索引
- 基于 DeepSeek 的知识库问答与引用片段返回
- 本地 H2 数据库持久化业务数据
- Nginx 单入口生产部署，前端与 API 同源访问
- 首次启动时可按环境变量初始化管理员账户

## 架构

| 组件 | 技术 | 默认端口 | 职责 |
| --- | --- | ---: | --- |
| 前端 | Vue 3 + Vite + Pinia | 5173（开发） | 登录、知识库、文档与对话界面 |
| 业务后端 | Spring Boot 2.7 | 8080 | 鉴权、业务数据、上传与问答编排 |
| RAG 网关 | FastAPI + Qdrant Client | 3001 | 文档解析、嵌入、向量检索与 LLM 调用 |
| 生产入口 | Nginx | 80 | 托管前端并将 `/api/` 反向代理至后端 |

生产环境的请求路径如下：

```text
浏览器 → Nginx :80
             ├─ /      → Vue 静态文件
             └─ /api/  → Spring Boot :8080 → RAG Gateway :3001
```

## 快速开始（本地开发）

### 1. 配置环境变量

在项目根目录复制示例文件：

```bash
cp .env.example .env
```

填写以下变量，切勿把真实值提交到 Git：

```dotenv
EMBEDDING_API_KEY=你的SiliconFlow密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn

DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com

JWT_SECRET=使用openssl-rand-hex-32生成的随机值
```

Windows PowerShell 可按需设置为当前会话环境变量，或使用对应的启动脚本读取 `.env`。

### 2. 启动 RAG 网关

```bash
cd rag-gateway
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# Linux/macOS：.venv/bin/pip install -r requirements.txt

.venv/Scripts/uvicorn server:app --host 127.0.0.1 --port 3001
```

健康检查：

```bash
curl http://127.0.0.1:3001/health
```

### 3. 启动后端

```bash
cd backend
mvn spring-boot:run
```

健康检查：

```bash
curl http://127.0.0.1:8080/actuator/health
```

### 4. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

访问 `http://localhost:5173`。

## 首次管理员账户

后端只会在管理员账户不存在时初始化一次管理员。建议在生产环境的 `.env` 中配置：

```dotenv
APP_BOOTSTRAP_ADMIN_USERNAME=admin
APP_BOOTSTRAP_ADMIN_PASSWORD=请设置至少12位的强密码
```

首次启动后，使用该用户名和密码登录。之后再次重启不会覆盖已有管理员密码。

> 不要使用 `admin123` 等弱密码，也不要将 `.env` 或密码提交到仓库。

## 生产部署（Ubuntu + Nginx）

以下方案适用于小型 Ubuntu 服务器。建议最少 2 GiB 内存，并启用 Swap。

### 1. 安装运行时

```bash
sudo apt update
sudo apt install -y nginx openjdk-17-jre-headless python3-venv python3-pip
```

### 2. 放置构建产物

在服务器创建目录：

```text
/opt/agent-cug/
├─ .env
├─ backend/agent-cug-backend-1.0.0-SNAPSHOT.jar
├─ frontend/dist/
└─ rag-gateway/
   ├─ server.py
   └─ requirements.txt
```

前端必须在上传前构建：

```bash
cd frontend
npm ci
npm run build
```

后端构建命令：

```bash
cd backend
mvn clean package -DskipTests
```

### 3. 运行 RAG 网关

```bash
cd /opt/agent-cug/rag-gateway
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server:app --host 127.0.0.1 --port 3001
```

生产场景建议将其配置为 `agent-cug-gateway.service` systemd 服务，并限制监听地址为 `127.0.0.1`。

### 4. 运行 Spring Boot 后端

```bash
cd /opt/agent-cug/backend
java -Xms128m -Xmx512m -jar agent-cug-backend-1.0.0-SNAPSHOT.jar
```

生产场景建议将其配置为 `agent-cug-backend.service` systemd 服务。

### 5. 配置 Nginx

将构建产物复制到 `/var/www/agent-cug`，并配置站点：

```nginx
server {
    listen 80 default_server;
    server_name _;

    root /var/www/agent-cug;
    index index.html;
    client_max_body_size 50m;

    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

检查并加载配置：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

安全组仅需对公网开放 `80`（以及受限来源的 SSH `22`）；不要暴露 `3001`、`8080` 或本地向量数据端口。

## API 概览

| 模块 | 路径前缀 |
| --- | --- |
| 认证 | `/api/auth` |
| 知识库 | `/api/knowledge-bases` |
| 文档 | `/api/documents` |
| 对话 | `/api/chat` |
| 后端健康检查 | `/actuator/health` |
| RAG 网关健康检查 | `/health` |

## 运维命令

```bash
# 查看服务状态
systemctl status agent-cug-gateway agent-cug-backend

# 重启服务
sudo systemctl restart agent-cug-gateway agent-cug-backend

# 跟踪日志
journalctl -u agent-cug-backend -f
journalctl -u agent-cug-gateway -f

# 本机健康检查
curl http://127.0.0.1:3001/health
curl http://127.0.0.1:8080/actuator/health
```

## 资源说明

`rag-gateway` 已使用轻量的本地 Qdrant 存储，不依赖运行完整的 AnythingLLM 服务。对于 2 GiB 内存的服务器，不建议同时部署 Docling、AnythingLLM 等重量级组件；网关会优先使用内置 PDF/DOCX 解析能力。

## 安全建议

- `.env` 权限应设置为 `600`：`chmod 600 .env`
- 使用强随机 `JWT_SECRET`，例如：`openssl rand -hex 32`
- API Key 泄露后应立即在对应平台撤销并重新生成
- 生产环境使用 HTTPS 时，应在 Nginx 配置 TLS 证书
- 为 SSH 配置密钥登录，并限制安全组来源 IP

## 开发与提交约定

- 不提交 `.env`、上传文件、H2 数据库、Python 虚拟环境与前端依赖目录
- 每次功能改动应先通过构建或相关测试，再提交到仓库
- 部署后应分别验证前端页面、后端健康检查与 RAG 网关健康检查
