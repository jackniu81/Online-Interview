# Design

## Context

全新仓库，仅有 docs/require.txt 与 OpenSpec 配置，无既有代码约束。需求见 proposal.md，行为契约见 specs/。已确认的决策输入：AI 走 OpenAI 兼容 API（环境变量配置）；评级阈值 ≥85 优秀 / ≥60 合格；后台单一管理员密码登录；全屏+录屏纳入末期阶段。需求文档"问题 1"（评分放前端还是后台）已定：**后台异步任务评分**，前端只提交答案。

## Goals / Non-Goals

**Goals:**
- 单仓库 monorepo：`admin/`（FastAPI）+ `frontend/`（React）+ docker-compose（PostgreSQL），本地一条命令可跑通
- 考试计时、题目顺序、答案保存均以服务端为权威，前端仅作展示与交互
- 评分异步化且崩溃可恢复（进程重启后未完成的评分能继续）

**Non-Goals:**
- 不做多管理员/角色体系、不做考试链接有效期与次数限制之外的防作弊对抗（如检测开发者工具）
- 不做分布式部署/水平扩展（单实例部署假设）
- 不做 AI 自动生成题目（30 道种子题人工编写入库）

## Decisions

### D1. 技术栈与目录
- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ asyncpg + Alembic + Pydantic Settings；包管理用 `uv`（或 pip + requirements.txt，实现时以 uv 优先）
- 前端：React 19 + TypeScript + Vite + react-router；Markdown 渲染用 react-markdown + rehype-highlight（代码高亮）；管理端与候选人端同 SPA，路由分区 `/admin/*` 与 `/exam`


### D2. 异步评分：进程内 asyncio 任务 + DB 状态恢复（不引入 Celery/Redis）
- 答案提交事务内将 `exam_answers.grading_status` 置为 `pending` 并立即返回；提交后 `asyncio.create_task` 执行评分协程（httpx 调 AI），成功写 `score/feedback/graded`，失败重试 3 次（指数退避）后置 `failed`
- 应用启动时扫描 `pending/grading` 状态的答案重新入队，保证进程重启不丢评分
- 全部题目到达终态（graded/failed）且考试已交卷时，计算平均分与总体状态（在同一评分协程尾部触发，DB 行锁防并发重复计算）
- 备选：Celery + Redis（拒绝：单实例场景运维成本过高）；FastAPI BackgroundTasks（拒绝：无持久化恢复语义，仍需自建扫描，不如统一为显式任务队列）
- 空答案直接记 0 分/"未作答"，不调 AI

### D3. 数据模型（核心表）
- `questions`：id、content（Markdown）、reference_answer、created_at；删除为硬删除（考试持快照，不受影响）
- `exams`：id、email、candidate_name、candidate_phone、question_count、duration_minutes、created_at、started_at、completed_at、total_score、result_status（excellent/pass/fail，评分完成前为 NULL）、recording_path
- `exam_questions`：exam_id、order、question_content、reference_answer（创建考试时随机抽题并快照，防止题库后续修改影响考试）
- `exam_answers`：exam_id、order、answer_text、submitted_at、score、feedback、grading_status（unanswered/pending/grading/graded/failed）；创建考试时按题数预生成 unanswered 行
- `proctoring_events`：exam_id、event_type（fullscreen_denied/fullscreen_exit/recording_denied 等）、occurred_at
- 列表"状态"派生规则：completed_at 为空 → 未完成；已交卷但仍有非终态评分 → 评分中；否则取 result_status

### D4. 考试链接与候选人会话
- 链接形如 `{FRONTEND_URL}/exam?t=<token>`；token 用 Fernet（cryptography 库，密钥来自环境变量）加密 `exam_id + email`，URL-safe，不含明文邮箱
- 候选人端接口以 token 换取考试信息；开始答题时服务端签发考试范围 JWT（sub=exam_id，有效期=时长+缓冲），后续答题/提交/事件上报接口用该 JWT 鉴权，与管理端 JWT（不同 audience）隔离
- 备选：仅凭 token 全程访问（拒绝：token 长期暴露在 URL，开始后用短时效 JWT 更安全）

### D5. 计时与自动交卷（服务端权威）
- 开始答题时写 `started_at`；剩余时间 = duration - (now - started_at)，所有查询接口返回 server_remaining_seconds，前端据此渲染倒计时
- 服务端双保险：① 开始时注册延时 asyncio 任务，到期执行自动交卷（未答题按空答案提交、写 completed_at、触发评分）；② 任何答题请求先做惰性超时检查，超时则先自动交卷再拒绝该请求；启动恢复时同样补建延时任务
- 提交答案校验：必须为当前最小未提交序号，已提交/越序/超时一律 4xx

### D6. 管理端鉴权
- 环境变量 `ADMIN_PASSWORD`；登录接口比对后签发 HS256 JWT（12h，aud=admin），FastAPI 依赖项统一校验；前端 axios 拦截器附带 token，401 跳登录页

### D7. AI 评分调用
- httpx 调 `{AI_BASE_URL}/chat/completions`，prompt 含题目、参考答案、候选人作答，要求返回 JSON `{"score": 0-100, "feedback": "..."}`；解析失败视为一次失败进入重试；评分标准（正确性/深度/完整性）写入 system prompt
- 配置：`AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`；未配置 API key 时应用可启动，评分任务直接置 failed 并在日志告警（便于无 AI 环境联调其余流程）

### D8. 前端答题交互
- 每页 1 题由服务端返回"当前题"驱动（无题目列表接口暴露全部题目内容），提交成功才返回下一题，天然防回退
- 屏蔽复制/粘贴：答题容器上拦截 copy/cut/paste/contextmenu 事件 + CSS user-select:none（题目区）；明确为 best-effort
- 交卷/超时后展示结果提示页；已完成考试再次进入直接显示"考试已完成"

### D9. 全屏与录屏（末期阶段）
- Fullscreen API 进入全屏，fullscreenchange 监听退出并上报事件；拒绝/不支持不阻断答题
- `getDisplayMedia` + MediaRecorder 录 webm，Blob 内存分片缓存，交卷后 multipart 上传至后端本地磁盘 `data/recordings/`，失败重试 3 次；明细页通过鉴权接口播放/下载
- 录屏需 HTTPS 或 localhost（浏览器约束），部署文档注明

### D10. 种子数据与初始化
- `admin/app/seed/questions.json` 存放 30 道人工编写的 AI agent 主观题（含参考答案）；CLI 命令 `python -m app.seed` 按题目内容哈希/标题判重，幂等插入
- Alembic 管理迁移；docker-compose 提供 PostgreSQL 16

## Risks / Trade-offs

- [进程内评分队列，单实例假设] → DB 状态 + 启动扫描恢复；若未来多实例需迁移到外部队列（模型已按状态机设计，迁移成本低）
- [复制/粘贴屏蔽可被开发者工具绕过] → 定位为 best-effort 威慑，配合录屏事后核查；不做对抗性检测
- [AI 返回非法 JSON 或评分漂移] → JSON 解析失败进重试；prompt 固定评分维度与输出格式；阈值判定不依赖 AI 主观结论
- [录屏文件大、上传失败] → webm 低码率录制、分片上传重试；失败不影响成绩，明细页标注缺失
- [getDisplayMedia 在 HTTP 部署下不可用] → 文档要求 HTTPS/localhost；拒绝授权时降级为事件记录
- [延时交卷任务与候选人主动交卷并发] → 交卷操作以 DB 条件更新（completed_at IS NULL）保证幂等，仅一方生效

## Migration Plan

全新系统无迁移负担：docker-compose 起库 → alembic upgrade head → seed → 启动前后端。回滚即停服务（无存量数据兼容问题）。

## Open Questions

- 录像保留时长/清理策略（不影响本次表结构与接口，可后续补定时清理任务）