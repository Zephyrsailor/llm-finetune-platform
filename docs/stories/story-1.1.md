# Story 1.1: 基础登录与账号管理

Status: Done

## Story

作为平台管理员，  
我希望平台提供安全的邮箱/密码登录与会话管理能力，  
以便团队成员能够在受控环境中访问工作空间并遵循审计要求。

## Acceptance Criteria

1. 支持邮箱注册、登录、登出流程，密码校验至少包含长度 ≥ 8、字母与数字组合，认证失败时返回泛化错误消息避免枚举账号。[来源: docs/epics.md]  
2. 使用 Access + Refresh Token（或等价 Session）管理会话，配置过期策略并提供手动注销接口，同时更新最后登录时间。[来源: docs/epics.md]  
3. 注册与“忘记密码”流程要求邮件验证码验证身份，验证码需设置过期时间与错误尝试上限。[来源: docs/epics.md]  
4. 完成密码重置流程：发送邮件链接、校验验证码后允许设置新密码，重置后旧 Refresh Token 立即失效。[来源: docs/epics.md]  
5. 在审计日志（`audit_logs` 表或等价实现）记录登录成功/失败事件，至少包含用户标识、IP、User-Agent、时间戳与事件类型。[来源: docs/epics.md]  
6. 密码采用 Argon2（或 bcrypt）哈希存储，登录接口具备速率限制或指数退避，满足平台安全与防爆破要求。[来源: docs/epics.md; docs/PRD.md]  
7. 提供匹配前端的 REST API（`/api/v1/auth/register|login|logout|refresh|password-reset` 等），并实现登录、注册、忘记密码、重置密码页面及成功/失败反馈。[来源: docs/epics.md; docs/architecture.md]

## Tasks / Subtasks

- [x] 定义数据模型与迁移脚本（AC#5, AC#6）  
  - [x] 最小化创建 `User` 与 `AuditLog` 表所需字段，并编写 Alembic 迁移验证。  
- [x] 实现后端认证流程（AC#1-AC#6）  
  - [x] 在 `backend/app/api/auth` 下实现注册、登录、登出、刷新、忘记密码、重置密码 API，复用 FastAPI + JWT，会话配置满足过期/注销要求。  
  - [x] 加入基础速率限制与验证码逻辑（开发模式可打印验证码），覆盖重置密码及尝试次数。  
  - [x] 依据 docs/Python编码规范与风格指南.md 编写 Pytest + TestClient 测试，验证主要成功/失败路径。  
- [x] 提供前端最小界面（AC#1, AC#3, AC#4, AC#7）  
  - [x] 在 `frontend/src/app/(auth)` 构建登录、注册、忘记密码、重置密码表单，与后端 API 对接并展示成功/失败提示。  
  - [x] 追加必要测试（单元或端到端）覆盖表单校验与流程跳转。  
- [x] 审计记录与文档（AC#5, AC#6）  
  - [x] 写入登录成功/失败审计日志，包含所需字段。  
  - [x] 更新运维文档说明速率限制、安全参数的配置来源，遵循最小实现，不引入额外系统。

## Dev Notes

### Requirements Context Summary

- 史诗 Epic 1 将 Story 1.1 定义为邮箱+密码注册、登录、退出、验证码重置与审计要求的基础登录能力，列出完整验收标准。[来源: docs/epics.md]
- PRD 强调安全性、操作审计与高可用（≥99.5% SLA），要求平台具备最小权限访问与失败重试能力。[来源: docs/PRD.md]
- 架构文档规划身份与权限模块位于 `backend/app/api/auth`、`core/security`，采用 FastAPI 单体、JWT/RBAC、Redis 速率限制与 Argon2 密码存储，并通过 Docker Compose 管理依赖。[来源: docs/architecture.md]

### Project Structure Notes

- 尚无已完成故事可提供经验复盘，当前为首个实现项。  
- 项目结构建议遵循架构文档中的 `backend/app/api/auth`, `backend/app/core/security`, `frontend/src/app/(auth)` 等路径，后端使用 FastAPI 单体 + Celery 目录划分，前端使用 React 组件与 hooks 分层。[来源: docs/architecture.md]

### References

- docs/epics.md#L20  
- docs/PRD.md#L9  
- docs/architecture.md#L1

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-28 | 初始草稿 | zephyr |
| 2025-10-28 | 补充后端/前端骨架与认证相关基础模型、迁移脚本 | zephyr |
| 2025-10-28 | 实现认证 API、验证码与前端多页面交互 | zephyr |
| 2025-10-28 | 前端自动化测试通过，故事标记为 Ready for Review | zephyr |
| 2025-10-29 | 修复验证码尝试上限逻辑并新增后端测试 | zephyr |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-1.1.xml

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

（待补充）

### Debug Log References

- 2025-10-28: 建立认证所需基础模型与仓储，新增 Alembic 初始迁移、数据库依赖与 SQLModel metadata。
- 2025-10-28: 完成认证 API、验证码与速率限制实现，新增 pytest 覆盖注册/登录/重置流程。
- 2025-10-28: 添加 React Testing Library + Vitest 测试用例；离线环境未能安装 npm 依赖，需联网后执行 `npm install` 再运行 `npm run test -- --run`。
- 2025-10-28: 执行 `npm run test -- --run`，4 项前端单测通过（React Router future flag 与 act 包裹提示保留为已知警告）。
- 2025-10-29: 修复验证码尝试次数限制并新增后端测试 `test_registration_verification_attempt_limit`，`python -m pytest` 全部通过。

### Completion Notes List

- 后端/前端骨架已搭建完毕，后续任务可在此基础上继续实现认证、验证码与速率限制逻辑。
- 认证端到端流程（注册、登录、刷新、重置密码）及审计日志均已落地；本地测试需先安装 `sqlmodel` 依赖后运行 `pytest`。
- 本地体验时可复制 `backend/.env.local` 为 `.env` 以使用 SQLite：`DATABASE_URL=sqlite:///./llmft.db`。
- 2025-10-28: 在 venv 安装依赖后执行 `python -m pytest`，5 项测试全部通过。


### Completion Notes
**Completed:** 2025-10-29
**Definition of Done:** All acceptance criteria met, code reviewed, tests passing
### File List

- backend/pyproject.toml
- backend/app/__init__.py
- backend/app/main.py
- backend/app/api/__init__.py
- backend/app/api/auth.py
- backend/app/api/router.py
- backend/app/core/config.py
- backend/app/core/database.py
- backend/app/core/rate_limit.py
- backend/app/core/security.py
- backend/app/models/__init__.py
- backend/app/models/user.py
- backend/app/models/audit_log.py
- backend/app/models/refresh_token.py
- backend/app/models/verification_code.py
- backend/app/repositories/__init__.py
- backend/app/repositories/user.py
- backend/app/repositories/audit.py
- backend/app/repositories/token.py
- backend/app/repositories/verification.py
- backend/app/schemas/auth.py
- backend/app/schemas/user.py
- backend/app/services/__init__.py
- backend/app/services/auth.py
- backend/app/services/errors.py
- backend/migrations/env.py
- backend/migrations/versions/0001_initial.py
- backend/alembic.ini
- backend/tests/test_health.py
- backend/tests/test_models.py
- backend/tests/test_auth_flow.py
- backend/.env.example
- backend/README.md
- backend/requirements-dev.txt
- frontend/package.json
- frontend/vite.config.ts
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/postcss.config.js
- frontend/tailwind.config.ts
- frontend/index.html
- frontend/src/main.tsx
- frontend/src/styles.css
- frontend/src/app/App.tsx
- frontend/src/app/router.tsx
- frontend/src/app/(auth)/LoginPage.tsx
- frontend/src/app/(auth)/RegisterPage.tsx
- frontend/src/app/(auth)/ForgotPasswordPage.tsx
- frontend/src/app/(auth)/ResetPasswordPage.tsx
- frontend/src/lib/api.ts
- frontend/src/app/__tests__/LoginPage.test.tsx
- frontend/src/app/__tests__/RegisterPage.test.tsx
- frontend/src/app/dashboard/DashboardPage.tsx
- frontend/src/setupTests.ts
- frontend/README.md

## Senior Developer Review (AI) - 2025-10-29

### Findings
- **High** (backend/app/repositories/verification.py:40-55; backend/app/services/auth.py:60-66,159-166)：验证码尝试次数未递增，`get_valid` 仅在验证码完全匹配时返回记录，错误输入不会更新 `attempts_made`，导致 `attempt_limit` 永远不会触发，攻击者可无限枚举验证码。建议在验证码校验失败时先获取记录并调用 `increment_attempts`，超过阈值后阻断后续请求。

### Tests Reviewed
- `python -m pytest`
- `npm run test -- --run`（React Router future flag 与 act 提示保留）

### Resolution
- 2025-10-29: backend/app/services/auth.py, backend/app/repositories/verification.py —— 验证码错误时递增 attempts 并在超限后删除记录；新增 pytest 用例验证尝试上限；前端文档同步更新。
