<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- PRD 治理章节要求提供流程看板、责任指派与提醒能力，帮助跨角色跟踪数据→训练→评估→部署链路。[来源: docs/PRD.md:56-57]
- 架构文档定义 `kanban_task`、`notification` 等治理实体，并指出需与 Deployment/Training 等模块状态同步。[来源: docs/architecture.md:72,161]
- UX 规范将 Governance 模块拆分为“流程看板/审批/通知中心”，强调看板需支持拖拽、指派、截止日期与提醒动效。[来源: docs/ux-specification.md:75,190,280]
- Implementation Readiness 报告确认 Kanban/Notification 为 Epic 6 核心能力，需在 Phase 5 之后的迭代落实。[来源: docs/implementation-readiness-report-2025-10-27.md:91]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与已有资产
- Story 5.3 已落地推理监控日志及审计体系，本故事应复用 AuditLog/Notification 框架，记录指派与提醒事件，保持审计一致性。
- Training/Evaluation/Deployment 服务已暴露运行状态，KanbanService 应直接读取既有表（training_jobs、evaluation_jobs、deployments、dataset_versions），避免重复存储。
- API 层延续 FastAPI + Pydantic 分层，路由挂载在 `/api/v1/governance/kanban`，依赖注入通过 `get_governance_service` 与 `PermissionService` 复用 RBAC。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 6.1: 流程看板与任务指派

Status: Done
<!-- story_header:end -->

## Story

作为项目经理，  
我希望在看板上分配任务并追踪进度，  
以便团队成员责任明确且能及时收到提醒。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 看板列出数据/训练/评估/部署各环节任务，状态与底层实体（dataset_version、training_job 等）同步，并支持拖拽调整优先级。
2. 支持指派负责人、设置截止日期与提醒时间，写入审计日志，并触发通知占位事件供后续通知中心复用。
3. 看板接口暴露 REST API：获取看板、创建手动任务、更新指派/提醒、批量调整顺序，权限需校验 `approval_manage`。
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 数据模型：新增 `kanban_cards` 表、枚举（Stage/Status/EntityType）及 Alembic 迁移。
- [x] 服务层：实现 `GovernanceKanbanService`，自动同步 dataset/training/evaluation/deployment 状态，生成审计与提醒占位事件。
- [x] API：新增 `/api/v1/governance/kanban` 路由（获取看板、创建、更新、reorder），校验权限并返回 Pydantic Schema。
- [x] 测试：编写集成测试覆盖看板读取、指派/提醒、拖拽排序与手动任务创建。
<!-- tasks_subtasks:end -->

## Validation

- `PYTHONPATH=.. venv/bin/pytest tests/test_runtime_monitor.py tests/test_governance_kanban.py`
- 通过 `/api/v1/governance/kanban/board` 验证看板包含自动同步的任务；通过 PATCH/POST 接口确认指派与手动任务逻辑正常。

## Notes

- 提醒暂以审计事件 `governance.notification.queued` 作为占位，后续 Story 6.3 将接入实际通知通道。
- 当底层实体状态变化时，刷新看板会自动调整列，用户手动拖拽仅影响排序；若需保留人工列变更可在后续故事扩展。

