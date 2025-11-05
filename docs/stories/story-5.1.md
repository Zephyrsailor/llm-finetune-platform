<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 5 Story 5.1 聚焦“模型注册与版本管理”，要求登记模型元数据、跟踪评估结果并以状态标签控制上线路径。[来源: docs/epics.md:276-284]
- PRD 明确平台需保存模型版本、训练参数、日志，并预留部署、多版本管理与回滚机制，支撑交付闭环的质量追踪。[来源: docs/PRD.md:40-46]
- 产品简报强调模型 artefact 需落地统一目录并预留外部模型仓库/CI 接口，确保后续扩展与灾备能力。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:150-179]
- 架构映射将 ModelRegistryService 归属部署与运营模块，需与 DeploymentManager、MetricsCollector 协同，并通过 Evaluation Gate Pattern 阻止未通过评估的模型上线。[来源: docs/architecture.md:63-113]
- UX 设计在部署流程中提供模型版本时间轴、候选/生产/回滚状态与评估入口，要求注册模块输出结构化信息供 UI 展示。[来源: docs/ux-specification.md:140-213]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 训练与评估域已有 `TrainingService`、`EvaluationService`、反馈闭环（Story 3.x/4.x），模型注册需复用训练运行、评估报告、反馈摘要，避免重复持久化逻辑。[来源: docs/stories/story-4.4.md:1-127]
- 平台核心模块规范推荐以 Domain Service + Repository 组织代码，并将 artefact 存放在 `/var/lib/llmft/models/{workspace}/{project}/{model_id}/v{n}`，需要与现有 datasets/training 目录保持一致。[来源: docs/tech-specs/platform-core-modules.md:1-200]
- Evaluation Gate Pattern 要求部署前校验最新评估指标，触发审批与回滚机制；模型注册流程需保留评估结果引用供部署模块复核。[来源: docs/architecture.md:86-104]
- 现有故事强调审计日志、RBAC、工作空间隔离（Story 1.x~4.x）；模型操作需继承审批/权限策略，尤其是 `approval_manage`、`deployment_manage` 角色。[来源: docs/architecture.md:63-113]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 5.1: 模型注册与版本管理

Status: Done
<!-- story_header:end -->

## Story

作为发布经理，  
我希望将训练完成的模型注册到平台模型仓库并维护版本状态，  
以便追踪上线合规性、快速回滚与对外交付。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 支持创建模型实体并登记基础信息（名称、归属项目、训练运行 ID、基础模型、超参摘要）、评估结果引用（最新评估任务、指标 JSON、报告路径）与部署状态字段，写入审计日志并遵循工作空间权限。[来源: docs/epics.md:276-284; docs/PRD.md:40-46]
2. 模型版本支持候选（candidate）/生产（production）/废弃（deprecated）等状态切换，记录操作者、时间戳、备注；生产态模型需关联上线目标环境与部署记录（若缺少则提示待部署）。[来源: docs/epics.md:276-284; docs/ux-specification.md:181-186]
3. 注册流程必须校验最新评估结果是否达标，未通过或缺失评估的版本禁止标记为生产；状态变更需广播事件供部署模块和通知中心消费。[来源: docs/epics.md:282-284; docs/architecture.md:94-104]
4. 前端提供模型版本列表/详情视图（含状态标签、评估信息、关联训练与部署入口），支持搜索/过滤、导出元数据，并允许在详情页触发状态变更与备注编辑。页面需兼容深色主题与可访问性要求。[来源: docs/ux-specification.md:181-213]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [ ] 后端：模型注册域服务与数据模型（AC1-AC3）
  - [x] 新增 `ModelRegistryService`、`ModelVersionRepository`、数据库迁移（`models`, `model_versions` 表），字段覆盖项目、训练运行、评估引用、状态、备注、指标摘要。[来源: docs/tech-specs/platform-core-modules.md:1-200]
  - [x] 实现 API：`POST /api/v1/models`、`POST /api/v1/models/{id}/versions`、`PATCH /api/v1/models/{id}/versions/{version_id}/status`、`GET /api/v1/models?workspace_id=...` 等，校验 RBAC 并写入审计日志。[来源: docs/architecture.md:63-113]
  - [x] 植入评估闸门：在创建/升级版本为 production 时校验 `EvaluationService` 指标，发布拒绝时返回明确错误并触发通知事件。[来源: docs/architecture.md:94-104]
  - [x] 将模型 artefact 存储路径对齐 `/var/lib/llmft/models/{workspace}/{project}/{model_id}/v{n}`，并落地元数据 JSON/manifest；记录创建/更新事件供部署模块订阅。[来源: docs/tech-specs/platform-core-modules.md:150-200]
- [ ] 前端：模型版本管理界面（AC2-AC4）
  - [x] 新增“模型仓库”页面与导航入口，展示模型列表、状态过滤、关联训练/评估摘要；实现版本时间轴、版本详情抽屉、状态切换对话框。[来源: docs/ux-specification.md:181-213]
  - [x] 接入 API（TanStack Query），提供导出按钮输出 JSON/Markdown，并在状态变更后刷新列表/提示结果。[来源: docs/ux-specification.md:181-213]
  - [x] 与评估报告、部署模块互链：从模型详情跳转到评估报告、部署页面；若评估未通过则展示阻断提示。[来源: docs/ux-specification.md:140-213]
- [x] 测试与文档
  - [x] 编写后端 pytest 覆盖模型注册、版本状态流转、评估闸门拒绝、审计事件；模拟无评估与失败评估分支。[来源: docs/architecture.md:86-104]
  - [x] 编写前端 Vitest/RTL 用例覆盖模型列表过滤、详情展示、状态切换表单验证、导出操作。[来源: docs/ux-specification.md:181-213]
  - [x] 更新 `docs/tech-specs/platform-core-modules.md`、`docs/architecture.md`、`docs/ux-specification.md` 对应章节，记录模型仓库接口、目录结构与 UI 流程；在故事完成后补充调试日志。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:150-179]
<!-- tasks_subtasks:end -->

## Dev Notes

- 模型注册需复用训练、评估域的现有 ID 与 artefact 路径，避免重复上传；评估指标缓存可存储在 `model_versions.metrics_json`，并提供字段表示评估时间与来源报告 ID。[来源: docs/architecture.md:86-104]
- 状态变更流程应触发事件总线（Redis Stream）并写入 `audit_logs`，以便部署模块和通知中心订阅；建议事件类型 `model.version.promoted`/`model.version.demoted`。[来源: docs/architecture.md:86-104]
- 针对候选/生产/废弃状态，需定义最小状态机（Candidate→Production→Deprecated，允许 Production→Candidate 回退），并记录操作者与备注以支持审计。[来源: docs/epics.md:276-284]
- 模型 artefact 与元数据遵循统一目录策略，并考虑定期保留策略（默认仅保留最近 5 个版本，可手动锁定）；注册服务需暴露 retention 标记接口.[来源: docs/tech-specs/platform-core-modules.md:150-200]

### Project Structure Notes

- 后端代码放置于 `backend/app/models/deployment.py`（或新建 `model_registry.py`）、`backend/app/repositories/model_registry.py`、`backend/app/services/model_registry.py`、`backend/app/api/model_registry.py`，遵循 Domain Service + Repository 模式。[来源: docs/architecture.md:63-113]
- 迁移文件位于 `backend/migrations/versions/`，命名 `0017_model_registry.py`（递增）；Artefact 目录在 `backend/app/services/model_registry.py` 中通过 `settings.workspace_storage_root` 构造。[来源: docs/tech-specs/platform-core-modules.md:150-200]
- 前端页面放在 `frontend/src/app/models/ModelRegistryPage.tsx` 与相关组件（时间轴、版本详情）；API 定义在 `frontend/src/lib/api.ts` 中 `modelRegistryApi` 命名空间，保持 TanStack Query key 规范。[来源: docs/ux-specification.md:181-213]

### References

- docs/epics.md:276-284
- docs/PRD.md:40-46
- docs/architecture.md:63-113
- docs/product-brief-llm-finetune-platform-2025-10-23.md:150-179
- docs/ux-specification.md:140-213
- docs/tech-specs/platform-core-modules.md:1-200
- docs/stories/story-4.4.md:1-127

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 17:20 UTC 梳理模型注册域需求与现有训练/评估实现，确定表结构、评估闸门与审计事件方案。
- 2025-10-31 18:05 UTC 完成 `RegisteredModel`/`ModelVersion` 数据模型、仓储、服务与 API，实现评估阈值校验及知识库导出，新增 Alembic 迁移与 pytest 覆盖。
- 2025-10-31 19:10 UTC 构建前端模型仓库页面与 TanStack Query 集成，实现状态切换、导出、评估/部署联动，并补充 Vitest 用例。
- 2025-10-31 19:40 UTC 更新技术规格、架构与 UX 文档，整理知识库路径及 UI 行为说明，准备故事交付。

### Completion Notes List

- 后端新增模型注册域（模型/版本表、仓储、服务、REST API、Alembic 迁移），通过 audit 事件与 Evaluation Gate 保护生产发布，并以 pytest 验证无评估与失败场景。
- 前端实现模型仓库界面：支持工作空间/项目筛选、版本时间轴、状态切换、导出与评估/部署快捷入口，补充 React Query 流程与 Vitest 测试。
- 文档与故事完成笔记同步更新，补充 ModelRegistryService 技术规格、架构交互、UX Flow 及组件说明。

### File List

- backend/app/models/model_registry.py
- backend/app/repositories/model_registry.py
- backend/app/services/model_registry.py
- backend/app/api/model_registry.py
- backend/app/api/router.py
- backend/app/api/deps.py
- backend/app/models/__init__.py
- backend/app/services/errors.py
- backend/app/repositories/workspace.py
- backend/app/repositories/evaluation.py
- backend/migrations/versions/0017_model_registry.py
- backend/tests/test_model_registry.py
- frontend/src/lib/api.ts
- frontend/src/app/models/ModelRegistryPage.tsx
- frontend/src/app/models/__tests__/ModelRegistryPage.test.tsx
- frontend/src/app/router.tsx
- docs/tech-specs/platform-core-modules.md
- docs/architecture.md
- docs/ux-specification.md
