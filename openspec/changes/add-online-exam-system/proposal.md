# Proposal

## Why

团队需要一个在线笔试系统来筛选 AI agent 方向的候选人：管理员维护主观题题库、为候选人生成专属考试链接，候选人限时在线作答，系统通过 AI 自动评分并给出总体评级，替代人工出题、发卷与阅卷的低效流程。当前仓库仅有需求文档（docs/require.txt），无任何实现。

## What Changes

- 从零搭建项目：FastAPI 后端 + React 前端 + PostgreSQL 数据库
- 管理后台：简单管理员密码登录（环境变量配置密码，JWT 会话）
- 题库维护：主观题（题目 + 参考答案）的增删改查；初始化 30 道 AI agent 相关题目
- 面试人员管理：输入邮箱创建考试，生成含加密邮箱参数的考试链接；题数可选 5/10/15/20（默认 5），时长可选 15/20/30/40 分钟（默认 15）；列表展示创建时间、完成时间、分数、状态，支持按状态（默认全部）与时间（默认近 1 周）过滤；明细页展示每题的 AI 评分与评价
- 候选人前端：通过加密邮箱参数进入，填写姓名、手机号并展示考试信息后开始答题
- 答题流程：右上角倒计时（归零自动提交全部）、每页 1 题、提交后不可回退、题目支持代码高亮、空白作答区、屏蔽复制/粘贴
- AI 评分：每题提交后由后台异步任务调用 OpenAI 兼容 API 生成评分（0-100）与评价并入库，不阻塞 UI；全部提交后按平均分计算总体状态（≥85 优秀，60-84 合格，<60 不合格）
- 防作弊（末期阶段）：答题时进入全屏、浏览器本地录屏并在交卷后上传

## Capabilities

### New Capabilities

- `admin-auth`: 管理员密码登录与后台接口鉴权
- `question-bank`: 主观题题库的维护（CRUD）与 30 道 AI agent 题目的初始化
- `exam-management`: 面试人员（考试场次）的创建、加密链接生成、列表过滤与明细查看
- `exam-taking`: 候选人身份登记、考试信息展示与限时逐题作答流程（倒计时、防回退、代码高亮、禁复制粘贴）
- `ai-grading`: 每题提交后的异步 AI 评分与评价、总体分数与状态（优秀/合格/不合格）计算
- `exam-proctoring`: 答题全屏与录屏采集上传（本次变更末期实现）

### Modified Capabilities

（无 —— 全新项目，无既有规格）

## Impact

- 新增全部代码：`admin/`（FastAPI、SQLAlchemy、Alembic、异步评分任务）、`frontend/`（React + Vite）
- 新增依赖：Python（fastapi、uvicorn、sqlalchemy、asyncpg、alembic、httpx、pyjwt、cryptography 等）；Node（react、react-router、代码高亮库等）
- 新增 PostgreSQL 数据库及迁移；开发环境提供 docker-compose
- 外部依赖：OpenAI 兼容 AI API（base_url / api_key / model 通过环境变量配置）
- 新增环境变量：数据库连接、管理员密码、JWT 密钥、链接加密密钥、AI API 配置