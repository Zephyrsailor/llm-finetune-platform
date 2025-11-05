<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 3 的第二个故事聚焦“向导式训练编排”，要求以分步向导引导数据科学家完成模型选择、数据绑定、资源配置与超参设定，降低启动训练门槛。[来源: docs/epics.md:142-147]
- PRD 的端到端流程强调：在数据准备完成后，用户可在 5 分钟内复制历史配置并发起新训练，向导需提供默认值、校验提示及草稿保存能力。[来源: docs/PRD.md:74-95]
- 架构文档说明训练模块通过 FastAPI + Celery 调度 GPU 任务，TrainingService/Training Log 等组件需提供作业状态、日志与 Artefact 目录，向导配置需与这些后端接口保持一致。[来源: docs/architecture.md:5-104; docs/tech-specs/platform-core-modules.md:56-140]
- UX 规范中“Training 模块”流程图 (Flow 2) 和导航结构要求向导具备步骤条、实时校验、草稿保存，以及与后续监控页面（日志、指标）联动。[来源: docs/ux-specification.md:60-140]
- 当前 Story 3.1 已落地训练模板库，可复用模板、参数校验与训练作业接口，为向导提供模板选择与参数加载能力。[来源: docs/stories/story-3.1.md; docs/stories/story-context-3.1.xml]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 后端已存在 TrainingService、TrainingTemplate/Job 模型与 Celery 占位任务；向导需在 API 层补充草稿、预校验与资源规划接口，保持 Repository/Service 分层一致。
- 数据侧依赖 Story 2.x 实现的 dataset_versions 与 dataset_format_versions，向导需校验所选版本已完成质量评估与格式标准化。
- 前端沿用 React + TanStack Query 结构，结合现有 Training 模块导航与模板库页面，增加向导步骤页、草稿存储（localStorage 或后端）与校验提示组件。
- 测试策略继续采用 pytest（后端）+ Vitest（前端），并复用 Story 3.1 中的 Celery eager/SQLite 配置进行集成测试。
- 审计与权限：操作需检查 `training_launch` 权限，所有重要动作（创建草稿、启动作业、取消作业）需写入 audit log，以保持治理链路完整。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 3.2: 向导式训练编排

Status: Done
<!-- story_header:end -->

## Story

作为数据科学家，  
我希望通过向导式界面完成模型选择、数据绑定、资源配置与超参调整，  
以便低门槛地复用模板并快速启动训练任务。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 提供多步骤向导（模板选择→数据集/版本→资源配置→参数确认→预览），每一步给出默认值、实时校验与错误提示，不完整配置不可进入下一步。[来源: docs/epics.md:142-147; docs/ux-specification.md:60-140]
2. 支持保存/恢复向导草稿，并可从历史训练任务复制配置，确保 5 分钟内完成新任务准备；草稿需与工作空间/用户关联。[来源: docs/epics.md:142-147; docs/PRD.md:74-95]
3. 向导完成后调用训练作业接口创建任务，展示启动结果（任务 ID、状态、日志入口），并记录审计日志；若校验失败需返回具体指引。[来源: docs/tech-specs/platform-core-modules.md:56-140; docs/architecture.md:69-104]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：扩展 TrainingService/API，新增草稿存储（SQLModel 表）、配置预校验端点、训练资源配置（GPU 数量/队列）参数处理；保证审计日志与权限校验覆盖。（AC#1, AC#2, AC#3）
- [x] 前端：实现向导页面与步骤条（与模板库共享 Training 导航），支持模板加载、版本选择、资源与超参表单、草稿保存/恢复、复制历史任务，完成提交后展示任务结果。（AC#1, AC#2, AC#3）
- [x] 联合体验：在向导中嵌入实时校验与提示（学习率范围、数据集质量状态、GPU 可用性），并在完成页提供日志/监控入口链接。（AC#1, AC#3）
- [x] 测试与文档：后端补 pytest（草稿 CRUD、配置校验、作业创建）；前端撰写向导交互测试；更新技术规格/UX 文档描述训练向导流程与草稿策略。（AC#1, AC#2, AC#3）
<!-- tasks_subtasks:end -->

## Dev Notes

- 草稿建议存储在 `training_wizard_drafts` 表（字段：workspace_id、user_id、payload JSON、updated_at）；对接 API `GET/PUT /api/v1/training/wizard/draft`。
- 数据校验需确认：所选数据集版本已完成质量评估，存在可用标准化格式；资源配置需检查 GPU 队列容量、并发限制（参考 `allow_parallel_gpu` 配置）。
- 向导默认参数可来自模板库；对于自定义输入（如 batch size、learning rate）沿用 TrainingService 中的参数规则（PARAMETER_RULES），在前端同步提示。
- 草稿复制历史功能可复用 `training_jobs` 最近成功作业的 `params_json` 与 `training_template_id`，并在 UI 提供“从历史复制”入口。
- 完成页应提供跳转至 Training Log/监控页面（Story 3.3 将实现），现阶段可提供占位链接或提示。

### References

- docs/epics.md:142-147  
- docs/PRD.md:74-95  
- docs/architecture.md:5-104  
- docs/tech-specs/platform-core-modules.md:56-140  
- docs/ux-specification.md:60-140  
- docs/stories/story-3.1.md  
- docs/stories/story-context-3.1.xml  

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-31 | 初始草稿 | Codex Agent |
| 2025-10-31 | 增补训练向导资源配置后端/前端实现、测试与文档 | Codex Agent |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-3.2.xml

### Agent Model Used

GPT-5 Codex（自动化代理）

### Debug Log References

- 2025-10-31 12:20 UTC 计划：
  1. 设计训练向导草稿/校验数据模型与 API，确保与 TrainingService、Celery 作业接口兼容。
  2. 实现前端向导步骤 UI、草稿保存/复制历史、提交训练任务，并补充交互校验。
  3. 编写后端/前端测试与文档更新，准备 Story 3.2 进入开发阶段。
- 2025-10-31 16:00 UTC 计划更新：
  1. 回顾 Story 3.2 接口与 UI 需求，确认差距并同步到调试记录。
  2. 逐步完善训练向导后端：草稿持久化、预校验、作业启动流程及审计日志/权限校验，并补充 pytest。
  3. 随后实现前端向导交互、草稿体验与文档更新，确保交付前具备完整测试。
- 2025-10-31 17:20 UTC 实施：
  - 为 `training_jobs` 增加 `requested_gpus`、`queue_name` 字段及迁移，扩展 TrainingService 校验逻辑（限制最大 GPU、合法队列、并行策略），同步审计日志输出。
  - 更新 Training API / Schema 与 pytest（`test_training.py`, `test_training_wizard.py`），覆盖资源配置成功与非法 GPU 场景。
  - 前端 TrainingWizardPage 引入四步流程，新增 GPU/队列输入、实时校验与校验结果展示；调整 API 客户端与 Vitest，模拟草稿保存与训练提交全流程。
  - 文档同步更新：Tech Specs 记录资源字段与校验策略，UX Spec 说明资源步骤交互；后端定向用例通过 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_training.py backend/tests/test_training_wizard.py -q`。

### Completion Notes List

- 2025-10-31：训练向导完成多步骤流程（模板→数据→资源→预览），提交时校验 GPU 数量与队列，并记录审计日志；后端通过 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_training.py backend/tests/test_training_wizard.py -q` 验证。
- 2025-10-31：在当前仓库环境运行 `pnpm vitest run src/app/training/TrainingWizardPage.test.tsx` 与 `TemplateLibraryPage.test.tsx`，确认草稿保存、校验与训练任务发起完整链路可用。

### File List

- docs/stories/story-3.2.md
- docs/sprint-status.yaml
- backend/app/core/config.py
- backend/app/models/training.py
- backend/app/services/training.py
- backend/app/tasks/training.py
- backend/app/api/training.py
- backend/app/schemas/training.py
- backend/migrations/versions/0010_training_job_resources.py
- backend/tests/test_training.py
- backend/tests/test_training_wizard.py
- frontend/src/lib/api.ts
- frontend/src/app/training/TrainingWizardPage.tsx
- frontend/src/app/training/TrainingWizardPage.test.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
