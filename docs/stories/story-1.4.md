# Story 1.4: 项目总览仪表盘（基础版）

Status: Done

## Story

作为项目负责人，  
我希望能够查看包含数据、训练、评估、部署等环节状态的项目总览仪表盘，  
以便及时了解进度、发现瓶颈并协调团队资源。

## Acceptance Criteria

1. 仪表盘按数据导入、训练、评估、部署 4 个环节展示状态（未启动/进行中/完成）以及负责成员，支持引用已有任务/日志来源。[来源: docs/epics.md#L74-L90]  
2. 每个环节提供 KPI 占位组件（例如数据量、训练轮次、最近评估得分），即使暂未接入真实指标也需给出布局与文案说明，供后续故事扩展。[来源: docs/epics.md#L74-L90; docs/PRD.md#L88-L104]  
3. 仪表盘支持按工作空间切换视图，并遵守工作空间与角色权限限制：只能看到当前账号有访问权限的项目与指标。[来源: docs/epics.md#L74-L90; docs/architecture.md#L60-L120]

## Tasks / Subtasks

- [x] 后端：构建 `DashboardService` 与 `GET /api/v1/dashboard/summary` 接口，聚合数据/训练/评估/部署环节的最新状态，并返回负责人与更新时间。（AC#1）  
  - [x] 为 `DashboardService` 编写单元测试，覆盖无项目、单项目、多项目及工作空间过滤等场景（`backend/tests/test_dashboard.py`）。（AC#1, AC#3）  
- [x] 后端：在 `DashboardService` 中预留 KPI 字段（如 `metrics` 占位列表），返回默认文案供前端说明。（AC#2）  
- [x] 前端：在 `frontend/src/app/dashboard/DashboardPage.tsx` 中实现仪表盘视图，渲染状态卡片、KPI 占位以及加载与空状态；集成工作空间下拉筛选。（AC#1, AC#2, AC#3）  
  - [x] 编写 React 测试（`frontend/src/app/__tests__/DashboardPage.test.tsx`），确保切换工作空间时请求参数正确、各环节卡片渲染及权限占位提示生效。（AC#1, AC#3）  
- [x] 权限与缓存：复用 `PermissionService` 校验工作空间访问权，并预留 Async Event Hub 订阅入口（当前使用轮询）。（AC#1, AC#3）  
- [x] 文档：更新 `docs/tech-specs/platform-core-modules.md` 与 `docs/ux-specification.md`，记录仪表盘组件结构与后续指标计划。（AC#2）

## Dev Notes

- 数据来源：`DashboardService` 当前聚合数据集清洗任务、训练/评估/部署审计事件和项目进度，最小版本基于 Query + AuditLog 聚合，后续可接入 Async Event Hub 实时刷新。[来源: backend/app/services/dashboard.py]
- 权限：接口使用 `PermissionService.require_operation(... RoleOperation.EVALUATION_VIEW)` 校验工作空间访问，前端在无权限/无项目时展示占位提示。[来源: backend/app/services/dashboard.py; frontend/src/app/__tests__/DashboardPage.test.tsx]
- 审计：仪表盘访问会写入 `audit_logs`（`dashboard.view`），记录工作空间范围与访问者信息。[来源: backend/app/services/dashboard.py]
- 测试：后端 pytest 覆盖 summary API（空数据、跨工作空间等），前端 Vitest 验证卡片渲染与工作空间切换交互。[来源: backend/tests/test_dashboard.py; frontend/src/app/__tests__/DashboardPage.test.tsx]

### Project Structure Notes

- Backend  
  - API：`backend/app/api/dashboard.py`（注册在 `router.py`）。  
  - Service：`backend/app/services/dashboard.py`，依赖现有 Repository/Service 聚合状态。  
  - Repository 扩展：如需新增查询，可放在 `backend/app/repositories/project.py`。  
  - Tests：`backend/tests/test_dashboard.py`。  
- Frontend  
  - 页面：`frontend/src/app/dashboard/DashboardPage.tsx`（或拆分 `DashboardOverview.tsx`、`StageStatusCard.tsx` 组件）。  
  - 数据访问：在 `frontend/src/lib/api.ts` 添加 `dashboardApi.summary()`。  
  - 状态管理：沿用 TanStack Query 缓存，Key 需包含 `workspaceId`。  
  - Tests：`frontend/src/app/__tests__/DashboardPage.test.tsx`。  
- 文档 & 运行  
  - `docs/tech-specs/platform-core-modules.md` 添加 Dashboard 模块章节；  
  - `docs/ux-specification.md` 记录卡片样式变化；  
  - 更新 `docs/backlog.md` 若引入后续 KPI 集成计划。

### References

- docs/epics.md:74-95  
- docs/PRD.md:88-104  
- docs/architecture.md:60-120  
- docs/ux-specification.md:20-240

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-29 | 初始草稿 | Codex Agent |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-1.4.xml

### Agent Model Used

（待补充）

### Debug Log References

- 2025-10-29 12:20 UTC 计划：
  1. 梳理现有 DashboardService 骨架与仓储接口，补齐审计日志查询、数据集/项目聚合依赖，确认需补充的 API、Schema 与测试结构。
  2. 完成后端 summary 接口：完善 DashboardService 聚合逻辑与访问审计，补充 FastAPI 路由及依赖注入，编写 pytest 覆盖空数据、跨工作空间与权限校验。
  3. 实现前端仪表盘：封装 dashboardApi.summary，构建 DashboardPage UI（工作空间切换、状态卡片、KPI 占位、加载/空态），并编写 React/Vitest 测试验证交互。
  4. 更新文档与故事记录，梳理后续实时刷新与指标接入 TODO，执行后端与前端测试作为回归。

### Completion Notes List

（待补充）

### File List

- docs/stories/story-1.4.md
