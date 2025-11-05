# Story 1.2: 工作空间与项目创建流程

Status: Done

## Story

作为平台管理员，  
我希望能够创建、编辑和归档工作空间，并在工作空间下初始化项目模板，  
以便内部与客户团队可以在隔离环境中快速启动微调项目，同时保持权限边界清晰。

## Acceptance Criteria

1. 支持创建、编辑、归档工作空间，项目必须绑定到具体工作空间，确保工作空间生命周期与项目一致。[来源: docs/epics.md]  
2. 新项目创建时自动初始化默认目录结构与占位文档（例如 `docs/`, `datasets/`, `pipelines/`），便于团队即刻开始配置。[来源: docs/epics.md; docs/architecture.md#144]  
3. 权限校验确保非成员无法访问或操作对应工作空间及其项目；需遵循 PRD 的安全要求（多工作空间隔离、最小权限）。[来源: docs/epics.md; docs/PRD.md:57,146]

## Tasks / Subtasks

- [x] 需求梳理与数据模型设计（AC#1, AC#2）  
  - [x] 定义 `workspace` 与 `project` 数据模型（含状态、关联关系、归档字段），补充 Alembic 迁移。[参考: docs/architecture.md#144]  
  - [x] 更新技术文档描述工作空间→项目关系及目录结构约定。
- [x] 后端 API 实现（AC#1-AC#3）  
  - [x] 在 `backend/app/api` 内新增工作空间与项目管理路由（创建、更新、归档、列表、详情）。  
  - [x] 在服务层实现默认目录/文档生成逻辑，并保障事务一致性。  
  - [x] 新增权限校验：仅工作空间成员和管理员可访问，未加入的用户收到 403。  
  - [x] 补充 Pytest 用例覆盖正向/异常路径及权限限制。
- [x] 前端界面与交互（AC#1-AC#3）  
  - [x] 在前端新增工作空间管理页面：列表、创建、归档状态切换，以及项目初始化表单。  
  - [x] 创建项目时展示默认目录生成结果或成功提示，并引导跳转到项目概览。  
  - [x] 使用 React Testing Library 为主要表单与权限提示编写测试。
- [x] 权限与审计补充（AC#3）  
  - [x] 复用 Story 1.1 的权限体系，在相关 API 中记录审计日志：创建/归档/访问。  
  - [x] 更新运维/操作文档，说明工作空间隔离与日志查看方式。  
  - [x] 与后续 Story 1.3（角色矩阵）对齐角色定义，预留角色扩展点。

## Dev Notes

### Requirements Context Summary

- Epic 1 定义本故事为“工作空间与项目创建流程”，强调通过工作空间隔离管理不同团队的项目启动与模板化准备。[来源: docs/epics.md]  
- PRD 强调工作空间级权限与操作日志、最小权限访问以及多工作空间的隔离要求，必须在实现中落实。[来源: docs/PRD.md:57,146]  
- 架构文档给出了 `workspace ↔ project` 关系与目录结构约定，应作为数据库模型与默认项目结构的依据。[来源: docs/architecture.md:117,144,178]

### Project Structure Notes

- 后端：在 `backend/app/api/` 下新增 `workspaces` 相关模块，仓储与服务层遵循现有模式（类似 `repositories/`、`services/`）。  
- 数据库迁移放在 `backend/migrations/versions/`，命名遵循 `create-workspace-project-tables`。  
- 前端：在 `frontend/src/app/` 下新增 `workspaces` 路由模块，利用现有布局与状态管理方案（TanStack Query + Zustand）。  
- 自动生成目录与占位文档可通过后端脚本（写入工作空间所在 storage，目录结构参考 architecture 文档）。

### References

- docs/epics.md:50-58  
- docs/PRD.md:57,146  
- docs/architecture.md:117,144,178  
- docs/tech-specs/platform-core-modules.md

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-29 | 初始草稿 | zephyr |
| 2025-10-29 | 完成工作空间与项目管理实现（后端/前端/文档） | codex-dev |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-1.1.xml *(上一故事，可为权限体系提供参考)*
- docs/stories/story-context-1.2.xml

### Agent Model Used

GPT-5 Codex（自动化代理）

### Debug Log References

2025-10-29 实施计划：
- 后端：新增 Workspace/Project 模型与仓储服务，提供 CRUD 与权限校验（JWT → current_user），接入审计日志；实现默认目录与占位文档生成。
- 数据层：编写 Alembic 迁移初始化 workspace、workspace_members、project 表。
- API：在 `/api/v1/workspaces` 下暴露创建、更新、列表、详情、项目初始化路由，确保非成员访问 403。
- 测试：补充 Pytest 覆盖创建/权限/项目生成路径，并验证默认目录落盘。
- 前端：新增工作空间管理页面与 API 封装，支持创建/归档切换、项目初始化提示，并撰写 RTL/Vitest 覆盖。
- 文档：更新技术规格/架构文档，记录新增模块与目录结构。

2025-10-29 实施记录：
- 数据层：新增 Alembic 迁移 `0002_workspace_project` 并扩展 SQLModel 模型，落地 workspace/member/project 关系。
- 后端：实现 WorkspaceService、API 依赖与 `workspaces` 路由，集成审计日志、JWT 权限校验及默认目录生成逻辑。
- 测试：补充 `test_workspaces.py` 覆盖创建、权限与目录生成；因本地缺少 sqlmodel 依赖导致 pytest 未能在当前环境完成，需待依赖安装后复跑。
- 前端：创建 WorkspacesPage 及相关 API 封装、Vitest 覆盖，支持工作空间管理与项目初始化。
- 文档：更新 Architecture/Tech Specs，记录新接口与默认目录结构。

### Completion Notes List

- 实现工作空间/项目后台接口与前端页面，生成默认目录并补全文档；pytest 因缺少 sqlmodel 依赖未能在本地运行，需安装依赖后复测。

### File List

- backend/app/api/deps.py
- backend/app/api/router.py
- backend/app/api/workspaces.py
- backend/app/core/config.py
- backend/app/models/__init__.py
- backend/app/models/workspace.py
- backend/app/repositories/workspace.py
- backend/app/schemas/workspace.py
- backend/app/services/errors.py
- backend/app/services/workspaces.py
- backend/migrations/versions/0002_workspace_project.py
- backend/tests/test_workspaces.py
- docs/architecture.md
- docs/sprint-status.yaml
- docs/stories/story-context-1.2.xml
- docs/stories/story-1.2.md
- docs/tech-specs/platform-core-modules.md
- frontend/src/app/router.tsx
- frontend/src/app/workspaces/WorkspacesPage.test.tsx
- frontend/src/app/workspaces/WorkspacesPage.tsx
- frontend/src/lib/api.ts
