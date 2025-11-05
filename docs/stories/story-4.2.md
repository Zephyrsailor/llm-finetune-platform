<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 4 的 Story 4.2 要求在训练完成后自动执行评估流水线，产出 BLEU/ROUGE/Exact Match/困惑度等核心指标，以便快速判断模型增益。[来源: docs/epics.md:231-238]
- PRD 的“评估与监控中心”强调评估需与训练任务联动、记录历史、可导出报告，并将结果作为质量闸门输入后续流程。[来源: docs/PRD.md:50-63]
- 架构文档将 EvaluationRunner、ReportBuilder 归入评估域，建议通过 Celery/Redis 事件自动化串联训练与评估，结合 Evaluation Gate Pattern 阻止指标退化的模型上线。[来源: docs/architecture.md:64-108]
- 技术规格已定义 `evaluation_jobs`/`evaluation_templates` 模型、artefact 目录 `/var/lib/llmft/{workspace}/{project|general}/evaluations/{job_id}` 与权限 `evaluation_view`，本故事需在此基础上扩展自动调度、指标写入与告警策略。[来源: docs/tech-specs/platform-core-modules.md:95-101; docs/tech-specs/runtime-operations.md:198-225]
- 训练模块（Story 3.x）现有 Celery 工作流、快照、监控/告警能力，可复用 TrainingService、TrainingMonitoringService 及 Redis 事件总线，将评估结果纳入实验管理与部署闸门。[来源: docs/tech-specs/platform-core-modules.md:56-94; docs/architecture.md:70-108]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 现有 `backend/app/services/evaluation.py` 与 `backend/app/tasks/evaluation.py` 已提供模板管理与手动触发任务，本故事应扩展其指标计算与训练联动逻辑，避免重复创建新服务。[来源: backend/app/services/evaluation.py; backend/app/tasks/evaluation.py]
- 训练完成后由 `backend/app/tasks/training.py::run_training_job` 更新运行状态，可在此或 TrainingService 层注入事件钩子/域服务调用，自动创建评估任务并写 `evaluation_jobs` 记录。[来源: backend/app/tasks/training.py:1-120]
- 监控/告警能力集中在 `TrainingMonitoringService` 与事件审计，可复用其评估指标阈值比较、告警分发模式，保持审计日志与权限校验一致。[来源: backend/app/services/training_monitoring.py]
- Story 4.1 已提供评估套件 UI 和手动触发接口，自动化流水线需在同一 API/前端结构上展示结果状态、指标回填与告警提示，避免新增独立页面。[来源: docs/stories/story-4.1.md]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 4.2: 自动化评估流水线

Status: Done
<!-- story_header:end -->

## Story

作为 ML 工程师，  
我希望训练完成后自动运行评估并生成指标，  
以便可以快速判断模型提升效果。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 当训练运行进入 `COMPLETED` 状态时，系统自动为该运行创建评估任务，执行 BLEU、ROUGE-L、Exact Match、困惑度等指标计算，可配置引用默认或自定义测试集，评估 artefact 落入约定目录。[来源: docs/epics.md:231-238; docs/tech-specs/platform-core-modules.md:95-101]
2. 评估结果（原始指标、基准对比、报告链接、执行日志）写入数据库并通过既有 `/v1/evaluations` API 暴露，同时在训练运行/实验管理视图展示最新指标与可追溯历史；评估任务的生命周期、审计日志与权限控制保持一致。[来源: docs/PRD.md:50-63; docs/architecture.md:64-108]
3. 评估失败或指标低于预设阈值时触发告警（通知渠道可复用训练监控规则），记录审计事件并在前端提供显著提示，供审批/部署前人工复核。[来源: docs/epics.md:231-238; docs/architecture.md:96-108; docs/tech-specs/runtime-operations.md:198-225]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端（AC#1）：扩展训练完成流程自动调度评估
  - [x] 在 `TrainingService` / `run_training_job` 完成分支中调用新域服务，将训练运行、模板、数据版本映射为待执行评估任务并写入 `evaluation_jobs`（含审计记录和触发模式）。
  - [x] 新增幂等机制与防抖（根据 run_id + template 去重）确保重复调度或手动触发不会生成重复任务。
- [x] 后端（AC#1, AC#2）：实现指标计算与结果持久化
  - [x] 为 EvaluationRunner 增加 BLEU、ROUGE-L、Exact Match、困惑度计算逻辑（集成 sacrebleu/rouge-score/evaluate），将结果写入 `metrics_json`、报告文件，并记录 baseline/delta/thresholds。
  - [x] 若训练运行提供基准指标（前一版本或手动设定），计算差异并存储在 `metadata_json.evaluation` 以支持阈值判断与历史追踪。
- [x] 后端（AC#2, AC#3）：扩展 API、告警与审计
  - [x] 扩展 `/v1/evaluations/jobs` 支持按 `training_run_id` 过滤并返回 `trigger_mode`；训练完成后自动写入审计 `evaluation.job.auto_created`。
  - [x] 在自动评估任务中加入阈值校验与告警逻辑，通过 `TrainingMonitoringService.record_evaluation_alert` 复用训练告警渠道并写入 `evaluation.alert.triggered` 审计。
- [x] 前端（AC#2, AC#3）：在训练与评估页面展示自动评估结果
  - [x] 在 `TrainingMonitorPage` 展示最新评估指标、delta/基线信息与阈值告警提示，保留导出与告警操作。
  - [x] 在评估套件页面标注自动触发任务、优化指标与阈值展示，并突出告警状态。
- [x] 测试与文档（AC#1-#3）：补充验证、更新规范
  - [x] 编写 pytest 覆盖自动调度、指标计算、阈值告警和失败场景，补充数据格式准备逻辑。
  - [x] 调整前端测试覆盖自动评估呈现与导出流程，更新技术规格、UX 规范描述自动化逻辑与依赖。
<!-- tasks_subtasks:end -->

## Dev Notes

- 自动化流程应复用 EvaluationRunner + Celery 队列，训练完成后通过域服务或 Redis 事件触发，不应在控制层直接耦合；需确保评估任务幂等并支持重试。[来源: docs/architecture.md:64-108; backend/app/tasks/training.py]
- 指标计算建议采用独立模块（可封装成 `metrics/evaluation_metrics.py`），并在 `metrics_json` 中记录原值、基准值、差异、统计时间，便于前端呈现与后续报告生成。[来源: docs/epics.md:231-238; docs/PRD.md:50-63]
- 告警策略可复用 TrainingMonitoringService 的规则/通知渠道，扩展指标类型和阈值配置；告警事件命名如 `evaluation.metric.degraded`，并映射 `evaluation_view` 权限。[来源: docs/tech-specs/runtime-operations.md:198-225; backend/app/services/training_monitoring.py]
- Artefact 目录应继续使用 `/var/lib/llmft/{workspace}/{project|general}/evaluations/{job_id}`，其中包含 `metrics.json`、`report.md`、必要的差异文件；注意清理策略与审计记录一致。[来源: docs/tech-specs/platform-core-modules.md:95-101]
- 需要评估新增依赖（如 sacrebleu、rouge-score、evaluate）的安装方式与许可，更新后端依赖锁定文件并在文档中说明。

### Project Structure Notes

- 后端改动集中于 `backend/app/tasks/training.py`、`backend/app/services/evaluation.py`、`backend/app/tasks/evaluation.py`、`backend/app/api/evaluation.py` 及相关仓储/模型（必要时新增 Alembic 迁移）。
- 如需新增告警服务，可置于 `backend/app/services/evaluation_alerts.py` 并扩展 `backend/app/repositories`.
- 前端更新位于 `frontend/src/app/training` 与 `frontend/src/app/evaluation`，同步调整 `frontend/src/lib/api.ts`、对应测试文件。
- 文档更新涉及 `docs/tech-specs/platform-core-modules.md`、`docs/ux-specification.md`、`docs/architecture.md` 的评估章节。

### References

- docs/epics.md:231-238 – 自动化评估流水线故事与验收标准  
- docs/PRD.md:50-63 – 评估与监控中心需求与导出要求  
- docs/architecture.md:64-108 – EvaluationRunner、ReportBuilder 及 Evaluation Gate Pattern  
- docs/tech-specs/platform-core-modules.md:56-101 – 训练/评估服务数据模型与 artefact 约束  
- docs/tech-specs/runtime-operations.md:198-225 – 权限与审计、告警策略  
- docs/stories/story-4.1.md – 评估模板与任务手动触发实现现状（可复用 UI/API）

## Dev Agent Record

### Context Reference

- docs/stories/story-context-4.2.xml
### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 13:45 UTC 审阅 PRD、Epic 4 与现有评估/训练实现，梳理自动化评估所需的触发流程、指标计算与告警约束，形成故事草稿。
- 2025-10-31 14:10 UTC 制定实现计划：① 梳理自动化需求与现状；② 实现训练完成自动调度、指标计算与告警等后端能力；③ 更新前端展示与交互；④ 补充测试与文档，确保满足 AC。
- 2025-10-31 15:30 UTC 复盘既有提交与测试差距，确定需补齐的后端告警逻辑、依赖声明、前端自动评估呈现及测试覆盖，锁定当前执行顺序。

### Completion Notes List

- 实现训练完成自动调度评估：`evaluation_jobs` 增加 `trigger_mode`，避免重复创建并记录审计；训练运行元数据同步维护最新指标与历史。 
- `evaluation.run_job` 使用 sacrebleu/rouge-score/evaluate 计算 BLEU、ROUGE-L、Exact Match、Perplexity，输出 baseline/delta/thresholds，并将低于阈值或失败场景通过 `TrainingMonitoringService` 写入统一告警。  
- 前端 `TrainingMonitorPage` 与 `EvaluationSuitePage` 展示自动评估卡片、阈值提示与“自动”徽章；增加 TypeScript 类型以支持扩展指标。  
- 后端新增 migration 与依赖声明（sacrebleu、rouge-score、evaluate），编写 `backend/tests/test_evaluations.py` 覆盖自动化、告警与失败路径；未运行前端整体测试（遵循用户限制）。

### File List

- backend/app/models/evaluation.py
- backend/app/models/training.py
- backend/app/models/__init__.py
- backend/app/services/evaluation.py
- backend/app/services/training_monitoring.py
- backend/app/tasks/evaluation.py
- backend/app/repositories/training.py
- backend/app/schemas/evaluation.py
- backend/migrations/versions/0015_evaluation_automation.py
- backend/pyproject.toml
- backend/tests/test_evaluations.py
- frontend/src/lib/api.ts
- frontend/src/app/training/TrainingMonitorPage.tsx
- frontend/src/app/evaluation/EvaluationSuitePage.tsx
- frontend/src/app/training/TrainingMonitorPage.test.tsx
- frontend/src/app/evaluation/EvaluationSuitePage.test.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
- docs/sprint-status.yaml

### Change Log

- 2025-10-31 13:45 UTC 创建初始草稿。
- 2025-10-31 16:20 UTC 落地 Story 4.2 自动化评估实现（后端告警与指标、前端展示、测试与文档更新）。
