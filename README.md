# 在线笔试系统（Online Interview）

面向 AI agent 方向候选人的在线笔试系统：管理员维护主观题题库并为候选人生成加密考试链接，候选人限时逐题作答，后台异步调用 AI（OpenAI 兼容 API）评分并产出总体评级（优秀/合格/不合格）。

技术栈：FastAPI + SQLAlchemy(async) + PostgreSQL + React 19 + Vite。

## 目录结构

```
admin/           FastAPI 后端（含异步评分任务、题库种子数据）
frontend/        React 前端（管理后台 /admin/* + 候选人考试 /exam）
docs/            需求文档
openspec/        OpenSpec 规格与变更工件
docker-compose.yml  本地 PostgreSQL
```

## 环境准备

- Python 3.12+、Node 18+、Docker
- 依赖管理：pip + venv（本机未安装 uv 时的备选，见 openspec design D1）

## 启动步骤

1. 启动数据库：

   ```powershell
   docker compose up -d db
   ```

   > 说明：因本机无法访问 Docker Hub，compose 暂使用本地已有的
   > `pgvector/pgvector:pg18` 镜像（PostgreSQL 18，行为兼容）；
   > 宿主端口用 5433（5432 被其他项目占用）。

2. 生成后端环境变量（首次）：

   ```powershell
   python -m venv admin\.venv
   admin\.venv\Scripts\python.exe -m pip install -r admin\requirements.txt -r admin\requirements-dev.txt
   admin\.venv\Scripts\python.exe admin\scripts\make_env.py   # 由 .env.example 生成 .env 并填充随机密钥
   ```

3. 数据库迁移与题库初始化：

   ```powershell
   Set-Location admin
   .venv\Scripts\alembic upgrade head
   .venv\Scripts\python.exe -m app.seed
   Set-Location ..
   ```

4. 启动后端（默认 http://127.0.0.1:8000）：

   ```powershell
   Set-Location admin
   .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

5. 启动前端（默认 http://localhost:5173，/api 自动代理到后端）：

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```

   Windows 上 Vite 可能仅监听 IPv6 `localhost`，浏览器请用
   `http://localhost:5173` 而非 `127.0.0.1`。

## 环境变量（.env，参考 .env.example）

| 变量 | 说明 |
|---|---|
| DATABASE_URL | PostgreSQL asyncpg 连接串 |
| ADMIN_PASSWORD | 管理员登录密码（单一账号） |
| JWT_SECRET | JWT 签名密钥（管理端与候选人会话共用密钥、不同 audience） |
| LINK_ENCRYPTION_KEY | Fernet 密钥，加密考试链接参数（make_env.py 自动生成） |
| AI_BASE_URL / AI_API_KEY / AI_MODEL | OpenAI 兼容评分 API；AI_API_KEY 留空可无 AI 联调（评分任务标记为失败） |
| FRONTEND_URL | 生成考试链接使用的公开前端地址 |

## 测试与构建

```powershell
# 后端测试
Set-Location admin; .venv\Scripts\python.exe -m pytest -q

# 前端构建
Set-Location frontend; npm run build
```

## 录屏功能约束

全屏与屏幕录制（`getDisplayMedia`）要求 **HTTPS 或 localhost** 环境；
生产部署必须配置 HTTPS，否则候选人端将降级为"仅记录拒绝事件"。
录像默认存储于 `admin/data/recordings/`（已加入 .gitignore）。
