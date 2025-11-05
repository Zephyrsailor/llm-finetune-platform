<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 5 Story 5.2 要求构建“一键 vLLM 部署流水线”，覆盖资源配置、健康检查与灰度发布，承接模型注册结果并输出访问凭证。[来源: docs/epics.md:288-295]
- PRD 部署与服务平台章节强调部署需绑定模型版本、生成 API/密钥、支持多版本对比、灰度发布与回滚，满足交付闭环要求。[来源: docs/PRD.md:45-48,78]
- 产品简报与技术决策文件要求使用 Docker Compose + vLLM 作为推理栈，预留 Triton/KServe 扩展与对象存储 artefact 路径，并定义健康检查与监控需求。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:35,106,162-169; docs/technical-decisions.md:11-25]
- 架构文档将 DeploymentManager/vLLM 作为 Epic 5 核心组件，规定从 ModelRegistry 事件驱动部署、使用 Redis/Celery 调度、Artefact 存放在 `/var/lib/llmft/models`、并记录 deployment_events/instances。[来源: docs/architecture.md:5-27,71,90-105,189-197]
- UX 设计在 Flow 3 中描述“登记模型版本、配置资源、健康检查、灰度发布、回滚/告警入口”的交互，要求前端提供部署表单、状态卡片与监控链接。[来源: docs/ux-specification.md:141-157]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- Story 5.1 提供了模型注册与评估闸门事件；本故事需复用 `RegisteredModel/ModelVersion`、审计日志与 artefact 目录，避免重复存储。[来源: docs/stories/story-5.1.md:1-140]
- 现有 TrainingService/EvaluationService 由 Celery 调度 GPU 作业并输出日志；部署流水线可沿用相同任务模式，实现 `deployment.deploy_model`、`deployment.rollback_model` 等任务，与 audit/notification 插件协同。[来源: backend/app/services/training.py; backend/app/tasks/evaluation.py]
- 技术规格提出 DeploymentManager 负责部署、滚动更新、回滚及健康检查；需与 Monitoring 模块共享指标，并记录 deployment_instances/events。[来源: docs/tech-specs/platform-core-modules.md:118-136]
- Implementation readiness report 建议使用 Compose + NVIDIA Toolkit 管理 vLLM 容器，并通过环境配置/模板控制资源规格，部署日志进入 Training Log 面板。[来源: docs/implementation-readiness-report-2025-10-27.md:46-95]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 5.2: vLLM 部署流水线

Status: Done
<!-- story_header:end -->

## Story

作为运维工程师，  
我希望在平台上一键将模型版本部署到 vLLM 集群并完成健康检查，  
以便业务方能获得可控的推理服务并快速灰度/回滚。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 后端提供部署 API（创建/更新/回滚/列表），支持选择模型版本、资源规格（GPU/并发/batch size）、目标环境，并写入 deployment_instances 与 deployment_events，伴随审计日志与工作空间权限校验。[来源: docs/epics.md:288-295; docs/architecture.md:71,90-105]
2. 部署任务执行前校验模型版本为生产状态且通过评估闸门，执行过程中触发 vLLM 容器启动、健康检查（模拟请求），成功后返回 endpoint/token；失败自动回滚并记录事件。[来源: docs/PRD.md:45-48,78; docs/product-brief-llm-finetune-platform-2025-10-23.md:35,168]
3. 支持灰度/版本切换流程：可暂停旧实例、保留并发限制，提供手动回滚 API；所有操作写入通知/审计并输出当前部署状态。[来源: docs/epics.md:288-295; docs/tech-specs/platform-core-modules.md:118-136]
4. 前端部署页面展示模型版本列表、部署表单、健康状态卡片、最近事件与监控入口，支持触发部署/回滚/灰度及下载凭证，遵循深色主题与可访问性规范。[来源: docs/ux-specification.md:141-157]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：部署域服务与任务实现（AC1-AC3）
  - [x] 新增 `Deployment`/`DeploymentInstance`/`DeploymentEvent` 数据模型及 Alembic 迁移，字段覆盖环境、资源配置、状态、凭证、健康检查时间、事件详情。[来源: docs/tech-specs/platform-core-modules.md:118-136]
  - [x] 实现 `DeploymentService`（+ Celery 任务）处理部署、灰度、回滚：读取 ModelRegistry artefact、生成 Compose 命令或 API 调用、写入实例记录与事件、触发通知。[来源: docs/architecture.md:90-105; backend/app/tasks/evaluation.py 类似结构]
  - [x] 暴露 API：`POST /api/v1/deployments`、`GET /api/v1/deployments`、`POST /api/v1/deployments/{id}/traffic`、`POST /api/v1/deployments/{id}/rollback` 等，结合 RBAC（deployment_manage）与审计记录。[来源: docs/PRD.md:45-48; docs/technical-decisions.md:11-25]
  - [x] 健康检查：向 vLLM endpoint 发送测试请求/llama token 校验，失败时自动回滚并生成 `deployment.failed` 事件；成功返回 endpoint/token。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:35,106,168]
- [x] 前端：部署管理 UI（AC4）
  - [x] 新增 `DeploymentPage` 与导航入口，展示可部署模型列表、部署表单（资源配置、环境选择、灰度选项）、状态卡片、最近事件、监控链接。[来源: docs/ux-specification.md:141-157]
  - [x] 接入部署 API（TanStack Query + mutations），支持部署、灰度切换、回滚、凭证导出，并在状态变化后刷新数据/提示结果。[来源: docs/ux-specification.md:141-157]
  - [x] 优化可访问性：表单标签、状态 badge、键盘导航、深色主题对比度；为 endpoint/token 提供复制/导出按钮。[来源: docs/ux-specification.md:4-38]
- [x] 测试与文档
  - [x] 编写后端 pytest 覆盖部署成功/失败/回滚场景，模拟健康检查通过/失败、未审批模型阻断、审计记录与事件写入；补充 Celery 任务单测（eager 模式）。[来源: docs/architecture.md:90-105]
  - [x] 编写前端 Vitest/RTL 用例覆盖部署表单校验、状态卡片渲染、API 调用与错误提示；Mock fetch 验证导出/回滚行为。
  - [x] 更新 `docs/tech-specs/platform-core-modules.md`、`docs/architecture.md`、`docs/ux-specification.md`，记录 DeploymentService 接口、目录结构、流程与 UI 交互；在故事完成后补充调试日志。
<!-- tasks_subtasks:end -->

## Dev Notes

- 部署任务应复用 ModelRegistry artefact 目录，按照 `/models/workspace-{id}/project-{id}/model-{mid}/v{n}` 复制模型权重，并在 `deployment_instances.manifest_path` 记录 Compose 配置，便于追踪与回滚。[来源: docs/tech-specs/platform-core-modules.md:118-136]
- 建议定义 Celery 队列 `deployment.execute`，串行处理同一 GPU 节点部署，确保与训练任务互斥；同时写入 audit (`model.version.deploy_requested`, `deployment.completed`, `deployment.rollback`).[来源: docs/technical-decisions.md:11-25]
- 健康检查可调用 vLLM `/health` 或执行一次简单推理（最大长度/超时），结果写入 `deployment_events`；失败后调用回滚任务恢复上一生产版本，并通知 NotificationHub。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:35,106,168]
- 前端部署页面需集成监控入口（跳转训练/部署监控页）及活动日志（最近事件列表），方便运维追踪；提供 API 密钥/endpoint copy-to-clipboard 功能并提示安全告警。[来源: docs/ux-specification.md:141-157]

### Project Structure Notes

- 后端新增文件：`backend/app/models/deployment.py`、`backend/app/repositories/deployment.py`、`backend/app/services/deployment.py`、`backend/app/api/deployment.py`、`backend/app/tasks/deployment.py`；迁移命名 `0018_deployment_pipeline.py`。  
- 现有 `model_registry` 事件需在部署服务监听，建议通过 Audit 事件或直接调用 service。  
- 前端页面位于 `frontend/src/app/deployment/DeploymentPage.tsx`（或 `ModelDeploymentPage.tsx`），API 在 `frontend/src/lib/api.ts` 下新增 `deploymentApi` 模块，遵循 TanStack Query key 规范。

### References

- docs/epics.md:288-295
- docs/PRD.md:45-48,78
- docs/product-brief-llm-finetune-platform-2025-10-23.md:35,106,162-169
- docs/technical-decisions.md:11-25
- docs/architecture.md:5-27,71,90-105,189-197
- docs/ux-specification.md:141-157
- docs/tech-specs/platform-core-modules.md:118-136
- docs/stories/story-5.1.md:1-140

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References
- 扩展部署域模型：新增 `DeploymentInstance` SQLModel、仓储与 `0019_deployment_instances` 迁移，确保部署数据落入 `deployments`/`deployment_instances`/`deployment_events` 三表。
- 调整 `DeploymentService` 及 API Schema，创建部署时同步生成实例记录，状态/流量/健康检查更新走统一事务；序列化结果新增 `instances` 列表满足验收条目。
- 同步技术规格、架构与 UX 文档，补充 `deployment_instances` 说明，并更新故事任务勾选。
- 全量执行 `PYTHONPATH=. backend/venv/bin/python -m pytest -q`，检视所有后端测试通过（Warning 仍为既有 `datetime.utcnow` 弃用提示）。

### Completion Notes List
- 文档：同步 DeploymentManager 章节、架构总览与 UX 规范，补充 vLLM 部署流程、事件记录与前端交互描述。
- 测试：`PYTHONPATH=. backend/venv/bin/python -m pytest -q` 全量通过，警告仅涉及外部依赖的 `datetime.utcnow` 弃用提示，后续统一治理。

### File List
- docs/stories/story-5.2.md
- docs/tech-specs/platform-core-modules.md
- docs/architecture.md
- docs/ux-specification.md
- docs/sprint-status.yaml
- backend/app/models/deployment.py
- backend/app/models/__init__.py
- backend/app/repositories/deployment.py
- backend/app/services/deployment.py
- backend/app/schemas/deployment.py
- backend/tests/test_deployments.py
- backend/migrations/versions/0019_deployment_instances.py

### Change Log
- 新增 `deployment_instances` 数据表与服务序列化逻辑，更新相关文档/故事记录，并执行完整后端 pytest，故事通过 QA/PO 验收，状态标记为 Done。
