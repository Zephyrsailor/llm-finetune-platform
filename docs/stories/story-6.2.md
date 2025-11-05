<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- PRD 将“合作友好”列为核心原则，要求平台提供多人协作、评论与批注能力，确保关键操作可追踪。[来源: docs/PRD.md:83-88]
- UX 导航结构在 Governance 模块下划分“审批与评论”，强调该子模块需与看板、通知联动呈现协作信息。[来源: docs/ux-specification.md:75-78]
- 评估报告布局预留“审批按钮、评论区、操作历史”侧栏，并在反馈面板中要求支持评论、附件与处理状态管理。[来源: docs/ux-specification.md:305-312]
- Epic 6.2 明确目标：支持 @mention、附件、可配置审批流，并将决策写入审计日志，权限遵循角色矩阵。[来源: docs/epics.md:345-356]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与已有资产
- 治理服务沿用 `AuditLogRepository`、`PermissionService` 与工作空间角色矩阵，复用现有 RBAC 审计模式保障审批可追踪。[来源: backend/app/services/governance.py]
- 评论与审批仓储扩展至 `backend/app/repositories/governance.py`，与看板共享 Session/事务边界，保证实体同步与性能一致性。[来源: backend/app/repositories/governance.py]
- API 层复用 `app/api/governance.py` 路由与依赖注入，通过 `get_governance_comment_service`、`get_governance_approval_service` 提供服务实例，维持模块化结构。[来源: backend/app/api/governance.py; backend/app/api/deps.py]
- Alembic 迁移 `0023_comments_and_approvals` 与治理模型集中于 `app/models/governance.py`，保证数据库结构与领域模型一一对应，便于后续通知中心与知识库复用。[来源: backend/app/models/governance.py; backend/migrations/versions/0023_comments_and_approvals.py]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 6.2: 多人协作评论与审批

Status: Done
<!-- story_header:end -->

## Story

作为业务审阅者，  
我希望在数据/训练/评估/部署流程中发表评论并发起审批，  
以便关键变更有记录、审批链可追踪。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 评论支持 @ 成员、附件、上下文描述，并校验目标实体归属及权限。
2. 审批请求可指定多名审核人，分别记录任务状态与意见，结果写入审计日志。
3. 评论/审批操作遵循 `approval_manage` 等角色权限，非授权成员仅可访问与自身相关记录。
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 数据模型：扩展治理模型引入评论与审批实体，新增 `governance_comments`、`approval_requests`、`approval_tasks` 表及枚举定义，并提交 Alembic 迁移。[来源: backend/app/models/governance.py; backend/migrations/versions/0023_comments_and_approvals.py]
- [x] 服务层：实现 `GovernanceCommentService` / `GovernanceApprovalService`，包含权限校验、@mention 过滤、审批决策聚合与审计事件写入。[来源: backend/app/services/governance.py]
- [x] API：在 `/api/v1/governance` 下新增评论与审批路由，补充 Pydantic Schema 与依赖工厂，按权限返回过滤后的结果。[来源: backend/app/api/governance.py; backend/app/schemas/governance.py; backend/app/api/deps.py]
- [x] 测试：编写集成用例覆盖评论创建/查询、审批多角色决策与审计日志验证，确保权限配置与流程闭环。[来源: backend/tests/test_governance_collaboration.py]
<!-- tasks_subtasks:end -->

## Validation

- `PYTHONPATH=/Users/zephyr/Desktop/workspace/jinfull/codex/llm-finetune-platform backend/venv/bin/pytest backend/tests/test_governance_collaboration.py backend/tests/test_governance_kanban.py`

## Notes

- 评论附件仅存储名称与 URL，占位实际文件托管；后续通知中心可基于 `governance.notification.queued` 事件分发提醒。
- 审批决策一旦全部完成即触发 `governance.approval.completed` 审计事件，为通报与知识库沉淀提供钩子；重复审批会被禁止，避免状态抖动。
