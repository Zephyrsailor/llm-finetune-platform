<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 6.3 要求通知中心支持 Webhook/IM/Email 多渠道，覆盖训练、告警、审批、部署等事件。[来源: docs/epics.md:360-368]
- 架构文档在治理模块中规划 NotificationHub，需与 Kanban/审批协同并支持企业微信/Slack/Webhook/Email。[来源: docs/architecture.md:72,92]
- UX 导航结构将“通知中心”列为治理子模块，要求展示可过滤的事件列表并跳转详情。[来源: docs/ux-specification.md:75-78,191]
- 既有故事（6.1/6.2）通过审计事件 `governance.notification.queued` 占位通知，Story 6.3 需将占位事件接入真实渠道并补充权限控制。[来源: docs/stories/story-6.1.md:31-32; docs/stories/story-6.2.md:51]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与已有资产
- 新增通知模型（channel/record）与 Alembic 迁移，放置于 `app/models/notification.py`，与现有 SQLModel 结构对齐并遵循审计字段约定。[来源: backend/app/models/notification.py; backend/migrations/versions/0024_notification_center.py]
- `NotificationService` 复用 `PermissionService`、`WorkspaceRepository`，在治理服务中直接注入，保持 RBAC 与审计流程一致。[来源: backend/app/services/notification.py; backend/app/services/governance.py]
- API 在 `/api/v1/notifications` 下提供渠道/事件管理，与现有 FastAPI 分层保持一致并通过依赖注入复用 session。[来源: backend/app/api/notifications.py; backend/app/api/deps.py]
- 审批/评论服务触发通知时仍写入审计日志，新增渠道发送逻辑在相同事务内提交，确保审计与通知状态一致。[来源: backend/app/services/governance.py]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 6.3: 通知与集成中心

Status: Done
<!-- story_header:end -->

## Story

作为运维工程师，  
我希望将平台事件推送到企业微信/邮箱等渠道，  
以便团队在现有工具中及时接收提醒并记录处理。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 工作空间可配置 Webhook/IM/Email 渠道，保存必要凭据并启停。
2. 渠道支持选择训练完成、训练告警、审批进度、部署状态等事件类型。
3. 事件投递失败会记录状态与错误信息，可手动重试并支持重试后回退至成功。
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 数据层：新增 `notification_channels` 与 `notifications` 表及枚举定义，提交 Alembic 迁移。[来源: backend/app/models/notification.py; backend/migrations/versions/0024_notification_center.py]
- [x] 服务层：实现 `NotificationService`，提供渠道 CRUD、事件分发、失败重试与文件/HTTP 投递逻辑；在治理服务注入并串联评论/审批/提醒事件。[来源: backend/app/services/notification.py; backend/app/services/governance.py]
- [x] API：新增 `/api/v1/notifications` 路由（渠道管理、事件列表、重试），补充 Pydantic Schema 与依赖，维持 RBAC 校验。[来源: backend/app/api/notifications.py; backend/app/schemas/notification.py; backend/app/api/deps.py]
- [x] 测试：编写集成用例覆盖渠道创建、评论提及触发通知、失败重试落盘；回归治理评论与审批测试确保事件联动成功。[来源: backend/tests/test_notifications.py; backend/tests/test_governance_collaboration.py]
<!-- tasks_subtasks:end -->

## Validation

- `PYTHONPATH=/Users/zephyr/Desktop/workspace/jinfull/codex/llm-finetune-platform backend/venv/bin/pytest backend/tests/test_notifications.py backend/tests/test_governance_collaboration.py backend/tests/test_governance_kanban.py`

## Notes

- Email 渠道采用本地 spool 方式落地 `.eml` 文件，避免依赖外部 SMTP；Webhook 支持 `http(s)` 与 `file://`，便于在无外网环境下回归测试。
- 失败通知记录会保留 `attempts/last_error/next_retry_at`，默认自动重试 2 次并允许通过 API 手动触发重试。
- 现阶段事件类型以治理场景为主（评论、审批、任务提醒）；训练/部署事件已在枚举中预留，后续故事接入即可复用渠道配置。
