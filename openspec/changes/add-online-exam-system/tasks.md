# Tasks

## 1. 项目脚手架

- [x] 1.1 创建 monorepo 结构（admin/、frontend/、docker-compose.yml 含 PostgreSQL 16（实际：Docker Hub 不可达，改用本地 pgvector/pgvector:pg18，宿主端口 5433）、.env.example 列出 DATABASE_URL/ADMIN_PASSWORD/JWT_SECRET/LINK_ENCRYPTION_KEY/AI_BASE_URL/AI_API_KEY/AI_MODEL/FRONTEND_URL），验证 `docker compose up -d db` 后数据库可连接
- [x] 1.2 初始化 FastAPI 后端（app 包、Pydantic Settings 读取环境变量、SQLAlchemy async 引擎与会话、/api/health 接口、pytest + httpx 测试基架），验证 `pytest` 通过 health 测试、`uvicorn` 可启动
- [x] 1.3 初始化 React + TS + Vite 前端（react-router 路由骨架 /admin/login、/admin/exams、/admin/questions、/exam，axios 实例与 API 代理配置），验证 `npm run build` 成功、dev server 可访问路由骨架
- [ ] 1.4 编写 README 开发文档（环境准备、启动步骤、环境变量说明、录屏需 HTTPS/localhost 的约束），验证按文档步骤可从零启动前后端

## 2. 数据模型与种子题库

- [x] 2.1 按 design D3 实现全部表模型（questions/exams/exam_questions/exam_answers/proctoring_events）并生成 Alembic 初始迁移，验证 `alembic upgrade head` 在空库成功建表
- [x] 2.2 编写 30 道 AI agent 相关主观题（含参考答案）到 app/seed/questions.json，实现幂等种子命令 `python -m app.seed`，验证首次执行入库 30 题、重复执行数量不变（含测试）

## 3. 管理端鉴权（admin-auth）

- [x] 3.1 实现 POST /api/admin/login（比对 ADMIN_PASSWORD、签发 12h HS256 JWT aud=admin）与管理端鉴权依赖，验证测试覆盖：正确密码返回 token、错误密码 401、无/过期 token 访问受保护接口 401
- [x] 3.2 实现前端登录页与 axios 拦截器（附带 token、401 跳转登录页），验证浏览器中错误密码提示、正确密码进入考试列表、未登录访问 /admin/* 重定向登录页

## 4. 题库维护（question-bank）

- [x] 4.1 实现题库 CRUD API（必填校验、分页列表按创建时间倒序、关键字搜索），验证测试覆盖：创建/编辑/删除、空题目或空参考答案 422、分页与搜索
- [x] 4.2 实现前端题库页（列表/搜索/新建/编辑弹窗/删除确认，Markdown 预览），验证浏览器完成一次增改删且列表即时反映

## 5. 考试管理（exam-management）

- [x] 5.1 实现创建考试 API：邮箱校验、题数 5/10/15/20 与时长 15/20/30/40 白名单校验、题库随机抽题快照到 exam_questions、预生成 unanswered 答案行、Fernet 加密生成考试链接，验证测试覆盖：默认参数、自定义参数、非法参数 422、题目不足报错、链接可解密还原且不含明文邮箱
- [x] 5.2 实现考试列表 API（状态派生：未完成/评分中/优秀/合格/不合格；状态过滤默认全部、创建时间范围过滤默认近 1 周、分页），验证测试覆盖各状态派生与组合过滤
- [x] 5.3 实现考试明细 API（候选人信息、考试参数、总分与状态、逐题题目/作答/评分/评价，未终态题目标记评分中/失败），验证测试覆盖未完成、评分中、已完成三种明细形态
- [x] 5.4 实现前端管理页：创建考试表单（邮箱输入 + 题数/时长选项列表，默认 5 题 15 分钟）、链接复制、列表页（状态/时间过滤器，默认全部+近 1 周）、明细页（逐题展示、评分中可刷新），验证浏览器走通创建→复制→列表过滤→明细查看

## 6. 候选人考试流程后端（exam-taking）

- [x] 6.1 实现 token 换取考试信息接口（解密失败/考试不存在返回统一无效错误；已完成考试返回已完成标记）与开始接口（姓名/手机号校验、写 started_at、签发考试范围 JWT、注册延时自动交卷任务），验证测试覆盖：无效/篡改 token、非法手机号、重复开始幂等、已完成考试拒绝
- [x] 6.2 实现当前题查询与答案提交接口（仅返回当前最小未提交序号题目；拒绝重复/越序/超时提交；提交置 grading_status=pending 并立即返回；最后一题提交触发交卷），验证测试覆盖：顺序提交、回退提交 4xx、末题提交后 completed_at 写入、剩余时间随服务端时间递减且刷新不重置（test_exam_answering.py）
- [x] 6.3 实现服务端自动交卷（延时任务 + 请求惰性超时检查双保险，空答案按空提交，completed_at IS NULL 条件更新保证幂等；启动时恢复未完成任务），验证测试覆盖：到期自动交卷、超时后提交被拒、主动交卷与超时任务并发仅一方生效

## 7. 候选人前端（exam-taking）

- [x] 7.1 实现信息登记页（解密进入、姓名/手机号表单校验、展示题数/时长/注意事项、无效链接与已完成提示页），验证浏览器：有效链接进入登记、篡改参数显示链接无效、已完成链接显示已完成
- [x] 7.2 实现答题页（右上角服务端倒计时、每页 1 题、react-markdown + rehype-highlight 渲染题目、空白 textarea 作答、提交后进下一题且无回退入口、末题提交/倒计时归零展示交卷结果页），验证浏览器完整答完一场考试且刷新后计时与进度不重置（新增 POST /api/exams/finish 支撑倒计时归零主动交卷，与延时任务并发仅一方生效）
- [x] 7.3 实现复制/粘贴/剪切/右键屏蔽（事件拦截 + 题目区 user-select:none），验证浏览器中 Ctrl+C/Ctrl+V/右键在题目区与作答区均被阻止

## 8. AI 异步评分（ai-grading）

- [ ] 8.1 实现 OpenAI 兼容评分客户端（httpx 调 chat/completions，system prompt 固定评分维度与 JSON 输出 {"score","feedback"}，解析校验 0-100 整数；未配置 API key 时置 failed 并告警），验证用 mock HTTP 的测试覆盖：正常解析、非法 JSON、越界分数、缺 key
- [ ] 8.2 实现进程内评分任务队列（提交后 asyncio.create_task、3 次指数退避重试、终态 graded/failed、空答案直接 0 分"未作答"不调 AI、启动扫描 pending/grading 恢复），验证测试覆盖：提交接口不被评分阻塞、重试后成功、重试耗尽置 failed 不影响其他题、重启恢复
- [ ] 8.3 实现总分与状态计算（全部终态且已交卷后按已成功评分题目平均分四舍五入，≥85 excellent / ≥60 pass / <60 fail，行锁防并发重复计算），验证测试覆盖：90→优秀、60→合格、59→不合格、含 failed 题目按其余计算、交卷后评分中列表显示评分进行中

## 9. 监考能力（exam-proctoring，末期阶段）

- [ ] 9.1 实现监考事件上报 API（考试 JWT 鉴权，记录 fullscreen_denied/fullscreen_exit/recording_denied 等）与录像上传/播放下载 API（multipart 存 data/recordings/、关联考试、管理端鉴权访问），验证测试覆盖：事件入库、上传后明细可取录像、未鉴权访问录像 401
- [ ] 9.2 前端实现开始答题时请求全屏与 getDisplayMedia 录屏（MediaRecorder webm 低码率、拒绝/不支持降级提示并上报事件、fullscreenchange 退出上报并提示重进、录制中断不阻塞答题），验证浏览器（localhost）：授权后全屏+录制、拒绝授权仍可答题且事件入库
- [ ] 9.3 前端实现交卷后录像后台上传（失败重试 3 次、不影响交卷结果）与管理端明细页监考区（事件列表、录像播放/下载、无录像标注），验证浏览器走通录制→交卷→上传→明细播放

## 10. 集成验证

- [ ] 10.1 端到端冒烟：seed 后登录→建题→创建 5 题 15 分钟考试→复制链接→登记→逐题作答（含代码块题）→交卷→AI 评分（可 mock）→明细核对分数与状态，验证全链路无错且列表状态流转正确（未完成→评分中→优秀/合格/不合格）
- [ ] 10.2 边界集成验证：倒计时归零自动交卷（未答题 0 分）、刷新续考、已完成链接重入、AI 全部失败时明细显示评分失败、后端重启后评分恢复，验证各场景行为与 specs 一致
- [ ] 10.3 运行全部后端测试与前端构建（`pytest`、`npm run build`），验证全部通过

## Workflow follow-up

- 实现完成并通过验证后，按项目评审要求归档本变更（openspec archive）。
- 归档后核对主 specs 与实现一致。