# Story 1.3: 角色与权限矩阵

Status: Done

## Story

作为安全负责人，  
我希望能够为工作空间定义并分配管理员、数据、训练、运维、业务审阅等角色及其权限，  
以便关键操作仅向被授权成员开放并满足审计与合规要求。

## Acceptance Criteria

1. 平台提供角色矩阵，覆盖管理员、数据、训练、运维、业务审阅角色，并定义其对数据导入、训练启动、部署发布、评估查看、审批等操作的权限范围。[来源: docs/epics.md]  
2. 角色管理界面允许管理员在工作空间内创建/编辑角色并为成员分配或撤销角色，变更即时生效且记录审计日志，可在治理模块查询历史。[来源: docs/epics.md; docs/PRD.md]  
3. 所有后端接口与前端功能均基于角色权限进行校验；未授权请求返回 403 并写入审计日志，同时预留 ABAC/SSO 扩展点满足最小权限与未来增强。[来源: docs/PRD.md; docs/architecture.md; docs/technical-decisions.md]

## Tasks / Subtasks

- [x] 角色模型与存储设计（AC#1, AC#2）  
  - [x] 在后端新增 `roles`、`role_permissions`、`workspace_member_roles` 模型/迁移，复用 Story 1.2 的 workspace 成员结构。[来源: docs/architecture.md]  
  - [x] 定义默认角色与操作集合（数据导入、训练、部署、评估、审批），并配置可扩展映射。  
  - [x] 更新技术文档记录角色矩阵与默认权限说明。
- [x] 权限校验与审计集成（AC#2, AC#3）  
  - [x] 扩展鉴权中间件，从 JWT/WorkspaceMembership 加载角色，校验 API / Celery /审批动作权限。  
  - [x] 将角色变更、权限拒绝写入 `audit_logs`，验证审计查询接口与日志可视化。  
  - [x] 编写 Pytest 覆盖角色变更即时生效、无权限返回 403、审计记录存在等场景。
- [x] 前端角色管理界面（AC#2）  
  - [x] 在 Settings/Workspace 管理下新增角色矩阵页面，展示角色权限、支持编辑成员绑定。  
  - [x] 实现角色创建/编辑表单与权限复选，操作成功后刷新并提示。  
  - [x] 使用 React Testing Library/Vitest 覆盖主要交互与权限提示流程（待安装前端依赖后执行）。
- [x] 文档与运维更新（AC#1-AC#3）  
  - [x] 更新 docs/tech-specs 与 docs/architecture，说明角色矩阵、扩展点与审计流程。  
  - [x] 更新运维手册，描述权限变更影响、回滚策略与批量脚本 TODO。  
  - [x] 视需要提供批量脚本导入默认角色/权限映射。

### Review Follow-ups (AI)

- [x] [AI-Review][Medium][Enhancement] 允许在 `scripts/roles_seed.py` 中指定具备 `approval_manage` 权限的执行账号（或自动选取拥有该权限的成员），避免随机成员缺权导致批量导入失败。

## Dev Notes

### Requirements Context Summary

- Epic 1 的 Story 1.3 需要提供管理员、数据、训练、运维、业务审阅等角色，确保关键操作仅向被授权成员开放。[来源: docs/epics.md]
- PRD 指出了工作空间级权限管理、最小权限和操作日志要求，是角色矩阵设计必须覆盖的安全约束。[来源: docs/PRD.md]
- 架构决策采用 JWT + RBAC + MFA，并结合 workspace 成员和审计日志机制，为本故事提供技术边界。[来源: docs/architecture.md]
- 技术决策明确“RBAC 为主，逐步增强 ABAC”，因此角色矩阵需预留扩展点。[来源: docs/technical-decisions.md]
- Story 1.2 已在工作空间管理中预留角色扩展点，本故事需复用该服务与审计框架扩展权限控制。[来源: docs/stories/story-1.2.md]

### Project Structure Notes

- 后端：在 `backend/app/models/`、`repositories/`、`services/` 中扩展角色/权限实体与关联；`api/` 暴露角色管理与权限校验端点；`core/security` 注入角色上下文。  
- 数据层：新增 Alembic 迁移维护角色、权限、成员角色关联表，与现有 Workspace 表联动。  
- 前端：在 `frontend/src/app/settings`（或 workspace 管理）新增角色矩阵组件与 API 封装。  
- 测试：后端 Pytest 覆盖角色校验与审计，前端 Vitest 覆盖角色 UI，必要时补充端到端场景。

### References

- docs/epics.md:52-63  
- docs/PRD.md:35-83  
- docs/architecture.md:25-172  
- docs/technical-decisions.md:36-61  
- docs/stories/story-1.2.md

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-29 | 初始草稿 | zephyr |
| 2025-10-29 | 标记为 Ready for Dev | codex-dev |
| 2025-10-29 | 落地角色管理 API 与前端界面，完善审计与单元测试 | codex-agent |
| 2025-10-29 | 交付批量导入脚本与运维指引，前端/后端测试通过，准备评审 | codex-agent |
| 2025-10-29 | Senior Developer Review (AI) 执行，结论：通过，记录 1 项后续跟进 | codex-review |
| 2025-10-29 | Senior Developer Review (AI) 复检，所有跟进项关闭 | codex-review |
| 2025-10-29 | 标记为 Done | codex-agent |
| 2025-10-29 | roles_seed 执行账号选择逻辑完善，后续跟进项关闭 | codex-agent |

## Dev Agent Record

### Context Reference

- docs/stories/story-context-1.3.xml

### Agent Model Used

GPT-5（Codex CLI）

### Debug Log References

- 2025-10-29 09:10 UTC 计划：
  1. 盘点现有 workspace 成员与审计模型，设计 `roles`、`role_permissions`、`workspace_member_roles` 表结构，明确唯一约束与外键关系，确保支持后续多角色绑定。
  2. 在 SQLModel 模型、仓储与 WorkspaceService 中接入上述实体，编写 Alembic 迁移初始化表结构，并为新建工作空间自动创建默认角色与权限映射。
  3. 定义默认角色矩阵（管理员、数据、训练、运维、业务审阅）与操作枚举，补充文档记录及单元测试覆盖成员角色写入与权限集合完整性。
- 2025-10-29 09:48 UTC 实施：新增 `backend/app/models/role.py` 及仓储/服务层逻辑，生成 Alembic 迁移 `0003_workspace_roles`，在 WorkspaceService 创建流程内引导默认角色注入并为 owner 绑定 `workspace-admin`；同步更新架构与技术规格文档描述角色矩阵，并扩充 `tests/test_workspaces.py` 验证默认角色与操作集按预期落地，`venv/bin/python -m pytest` 全量通过。
- 2025-10-29 10:05 UTC 实施：引入 `PermissionService` 聚合角色权限，约束工作空间更新/项目创建操作并在拒绝时写入 `audit_logs`；更新 `tests/test_workspaces.py` 验证 403 响应与审计日志生成，同时确保角色赋权后操作恢复。
- 2025-10-29 10:42 UTC 实施：完成角色管理 API（列表/创建/更新、成员角色绑定）与审计事件；前端 `WorkspacesPage` 新增角色矩阵视图、角色表单及成员勾选交互，更新 `workspaceApi` 并补充 React 单测（受限于缺少 pnpm 未执行）。
- 2025-10-29 10:55 UTC 下一步计划：
  1. 补充 docs/tech-specs、docs/architecture 文档与故事记录，标注角色管理前后端实现细节。
  2. 评估前端依赖安装方案，待环境可用后执行 Vitest 用例并记录结果。
  3. 跟踪批量导入脚本实现计划（TODO 保留）。
- 2025-10-29 11:08 UTC 测试：安装前端依赖并执行 `pnpm test -- --runTestsByPath src/app/workspaces/WorkspacesPage.test.tsx`，用例通过验证角色矩阵交互。

### Completion Notes List

- 2025-10-29：落地工作空间角色/权限表结构与默认矩阵，文档同步更新；`backend/venv/bin/python -m pytest` 全量通过。
- 2025-10-29：上线角色管理 API 与前端矩阵视图，新增审计事件与后端集成测试；更新运维手册说明回滚策略；前端 `pnpm test -- --runTestsByPath src/app/workspaces/WorkspacesPage.test.tsx` 通过；提供批量导入脚本 `scripts/roles_seed.py`（dry-run 支持）。
- 2025-10-29：Senior Developer Review (AI) 完成，建议补充脚本执行账号选择能力，状态更新为 Review Passed。

### File List

- backend/app/models/__init__.py
- backend/app/models/role.py
- backend/app/repositories/role.py
- backend/app/schemas/role.py
- backend/app/services/role_management.py
- backend/app/services/permissions.py
- backend/app/services/roles.py
- backend/app/services/workspaces.py
- backend/app/api/deps.py
- backend/app/api/workspaces.py
- backend/migrations/versions/0003_workspace_roles.py
- backend/tests/test_workspaces.py
- docs/architecture.md
- docs/stories/story-1.3.md
- docs/stories/story-context-1.3.xml
- docs/tech-specs/platform-core-modules.md
- frontend/src/lib/api.ts
- frontend/src/app/workspaces/WorkspacesPage.tsx
- frontend/src/app/workspaces/WorkspacesPage.test.tsx
- scripts/roles_seed.py
- docs/tech-specs/runtime-operations.md
- docs/backlog.md

## Senior Developer Review (AI)

**结论**：通过  
**审阅日期**：2025-10-29  
**审阅人**：codex-review  

### 审阅摘要
- 后端 RoleManagementService 与角色矩阵 API 正常运行，`backend/venv/bin/python -m pytest tests/test_workspaces.py` 全部通过。
- 前端 WorkspacesPage 角色矩阵交互及成员授权流程测试通过（`pnpm test -- --runTestsByPath src/app/workspaces/WorkspacesPage.test.tsx`）。
- 批量导入脚本已支持显式或自动选择具备 `approval_manage` 权限的执行账号，本轮复检未发现新增问题。

### 发现与严重级别
- 无新问题。

### 测试记录
- `backend/venv/bin/python -m pytest tests/test_workspaces.py`
- `pnpm test -- --runTestsByPath src/app/workspaces/WorkspacesPage.test.tsx`

### 行动项
- 无。

### 状态
- Story 状态：Review Passed（评审通过）。  
- sprint-status.yaml：保持 `review`，后续流程可根据需要同步。
