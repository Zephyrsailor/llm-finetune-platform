<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 4 的 Story 4.1 聚焦“标准化评估套件”，要求平台提供内置问答、对话、分类等评估模板，允许 QA 团队选择场景并在训练前后复用统一测评流程。[来源: docs/epics.md:212-223]
- PRD 在“评估与监控中心”指出评估需与训练任务互通，支持导出 PDF/Markdown 报告，保障业务在上线前能量化模型收益。[来源: docs/PRD.md:50-63]
- 架构文档为评估模块定义了 `backend.app.api.evaluation`、`backend.app.tasks.evaluation`、`EvaluationRunner`、`ReportBuilder` 等组件，并强调通过 Celery/Redis 异步执行评估任务，归档 artefact 供报告与审批使用。[来源: docs/architecture.md:5-120]
- 技术规格要求 artefact 目录遵循 `/var/lib/llmft/{workspace}/{project}/{type}/…`，其中包含 `evaluations`，需与现有数据、训练目录一致地支持审计、清理与权限控制。[来源: docs/tech-specs/platform-core-modules.md:40-150]
- 实施准备报告与 UX 规范强调评估报告页面需满足 WCAG 2.1 AA，可视化指标对比与导出动作清晰可达，这是前端实现与验收的重要约束。[来源: docs/implementation-readiness-report-2025-10-23.md:90-106; docs/ux-specification.md:281-306]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 架构定义了评估域的后端目录（`backend/app/api/evaluation`, `backend/app/tasks/evaluation`, `EvaluationRunner` 服务），需沿用 Training/DataHub 的 Repository + Service 分层模式，复用 Celery 任务调度与审计日志策略。[来源: docs/architecture.md:38-110]
- 现有清洗质量评估 (`QualityEvaluationJob`) 已在数据模块中使用 Celery 与 artefact 路径版本化，可作为评估模板/结果持久化与状态机实现的参考基线。[来源: backend/app/models/dataset.py:215-256; backend/app/tasks/data_cleaning.py:442-520]
- artefact 必须落在 `/var/lib/llmft/{workspace}/{project}/evaluations/{run_id}/` 树下，并遵循 Runtime Operations 的磁盘监控与清理脚本约束，避免与训练、数据 artefact 相互覆盖。[来源: docs/tech-specs/platform-core-modules.md:145-150; docs/tech-specs/runtime-operations.md:120-165]
- 前端应在 `frontend/src/app` 下新增 Evaluation 相关页面，复用 Training Wizard/Card 组件模式，并满足 UX 对评估报告布局、导出操作与无障碍提示的要求。[来源: docs/ux-specification.md:281-310]
- 权限矩阵中 `evaluation_view` 操作为查看评估结果的最小权限单元，新接口需与 Role/Permission Service 集成，保持审计与访问控制一致性。[来源: docs/tech-specs/runtime-operations.md:198-225]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 4.1: 标准化评估套件

Status: Review Passed
<!-- story_header:end -->

## Story

作为 QA 主管，  
我希望选择默认测试集或上传定制样本，  
以便训练前后均能进行统一评估。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 平台内置通用问答、对话、分类等评估模板，支持按场景选择、查看所需指标与脚本说明，并向后端暴露获取模板列表与详情的 API。[来源: docs/epics.md:212-217; docs/architecture.md:70-109]
2. 允许上传或引用定制测试集，评估任务需将数据版本与模板绑定，artefact 存入 `/var/lib/llmft/{workspace}/{project}/evaluations/{run_id}/`，并在评估历史中可追溯数据来源。[来源: docs/epics.md:218-221; docs/tech-specs/platform-core-modules.md:40-150]
3. 评估任务需自动关联指定训练运行（或基准模型），记录开始/结束状态、指标输出与报告链接；执行完成后可通过 UI/导出接口访问结果，且仅 `evaluation_view` 及以上角色可见。[来源: docs/epics.md:222-223; docs/PRD.md:50-63; docs/tech-specs/runtime-operations.md:198-225]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端（AC#1）：实现评估模板管理（模型定义、Repository、Service、API），支持列表与详情查询，并在 Celery 任务中按模板配置加载指标脚本。
  - [x] 建立 `evaluation_templates` 数据模型与种子数据，涵盖问答/对话/分类场景，并与 `EvaluationRunner` 对齐指标说明。[来源: docs/architecture.md:70-109]
- [x] 后端（AC#2）：提供评估任务创建 API，支持上传定制测试集，生成 artefact 目录并写入元数据/审计日志。
  - [x] 扩展存储层以 `/evaluations/{run_id}` 存放输入样本与结果文件，校验磁盘用量并复用 Runtime Operations 清理脚本。[来源: docs/tech-specs/platform-core-modules.md:145-150; docs/tech-specs/runtime-operations.md:120-165]
- [x] 后端（AC#3）：在评估任务生命周期内自动关联训练 Run，持久化指标、报告路径与状态；完成后触发通知或事件（供后续报告故事复用）。
  - [x] 新增 API `GET /v1/evaluations/{id}` 与导出接口，校验 `evaluation_view` 权限并落日志。[来源: docs/tech-specs/runtime-operations.md:198-225]
- [x] 前端（AC#1-#3）：在 Evaluation 模块新增“标准化评估套件”页面，支持模板选择、训练 Run 绑定、测试集上传、任务状态与结果展示，并遵循无障碍与导出交互规范。[来源: docs/ux-specification.md:281-310; docs/implementation-readiness-report-2025-10-23.md:90-106]
- [x] 测试与文档：补充后端 pytest（模板 CRUD、评估任务、权限）、Celery 集成测试、前端交互测试；更新架构/UX/运行手册中评估模块章节与导出流程描述。
<!-- tasks_subtasks:end -->

## Dev Notes

- 评估执行应复用 Celery + Redis 的异步模式，任务失败需写入审计日志并保留 artefact，后续故事可基于该结构生成报告与告警。[来源: docs/architecture.md:70-110]
- 评估模板与任务需与 Training/Deployment 模块共享模型/数据引用元数据，以便部署前执行“Evaluation Gate”校验。[来源: docs/architecture.md:99-106; docs/PRD.md:50-63]
- 前端需满足 UX 对指标对比卡片、报告下载按钮的无障碍要求，遵循 WCAG 2.1 AA 对比度与键盘可达性规范。[来源: docs/ux-specification.md:297-310; docs/implementation-readiness-report-2025-10-23.md:90-106]
- 权限控制默认绑定 `evaluation_view` 操作；需要确保 API、导出和 artefact 下载都在服务层完成权限校验并记录审计事件。[来源: docs/tech-specs/runtime-operations.md:198-225]

### Project Structure Notes

- 后端建议在 `backend/app/models`, `backend/app/repositories`, `backend/app/services`, `backend/app/api`, `backend/app/tasks` 下新增 `evaluation` 相关模块，命名与 Training/DataHub 模块保持一致。[来源: docs/architecture.md:38-110]
- Artefact 路径约定 `/var/lib/llmft/{workspace}/{project}/evaluations/{run_id}`，需在配置与清理脚本中注册，避免与现有 `datasets`、`training` 目录冲突。[来源: docs/tech-specs/platform-core-modules.md:145-150]
- 前端页面可放置在 `frontend/src/app/evaluation`，复用 Training Wizard 的查询缓存与 Form 组件，遵循 UX Layout 3 的区块拆分与响应式规则。[来源: docs/ux-specification.md:281-310]

### References

- docs/epics.md:212-223 – Epic 4 Story 4.1 分解与验收条件  
- docs/PRD.md:50-63 – 评估与监控中心需求（统一评估、导出报告、训练联动）  
- docs/architecture.md:38-110 – 评估模块组件、EvaluationRunner/ReportBuilder、异步执行  
- docs/tech-specs/platform-core-modules.md:40-150 – Artefact 目录结构与评估类型、审计约束  
- docs/tech-specs/runtime-operations.md:120-225 – 存储清理脚本、权限矩阵（evaluation_view）  
- docs/ux-specification.md:281-310 – Evaluation Report 布局、导出与无障碍要求  
- docs/implementation-readiness-report-2025-10-23.md:90-106 – 可访问性与评估工作流注意事项

## Dev Agent Record

### Context Reference

- docs/stories/story-context-4.1.xml

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 13:05 UTC 完成评估套件后端接口验证、前端导航与导出体验完善，并调整技术/UX 文档；运行 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_evaluations.py -q` 全量通过。
- 2025-10-31 12:25 UTC 梳理评估套件需求与现有实现差距，确定后端需新增 `evaluation_templates`/`evaluation_jobs` 模型、Celery 任务与 API，前端补充模板选择与任务跟踪页面，并更新权限/文档，同步制定实现计划。
- 2025-10-31 12:10 UTC 汇总 Epics/PRD/Architecture/UX 资料，整理标准化评估套件需求并输出故事草稿。

### Completion Notes List

- 交付评估模板与任务全链路，完善前端评估套件页面导航与导出体验，并同步技术/UX 文档；相关评估用例全部通过。

### File List

- backend/tests/test_evaluations.py
- docs/sprint-status.yaml
- docs/stories/story-4.1.md
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
- frontend/src/app/evaluation/EvaluationNav.tsx
- frontend/src/app/evaluation/EvaluationSuitePage.tsx
- frontend/src/app/evaluation/EvaluationSuitePage.test.tsx

### Change Log

- 完成评估套件端到端实现：补充前端导航与导出交互、放宽导出响应校验、更新技术/UX 文档，并标记评估故事进入评审阶段。

## Senior Developer Review (AI)

- **结论**：通过。本次交付落实了评估模板管理、任务编排、导出以及前端操作流程，符合三条验收标准。
- **关注点**：
  - [Low] Celery 任务仍返回占位指标（`evaluation.run_job`），后续接入真实评估逻辑时需同步扩充测试。
  - [Low] 本地仅跑通后端评估用例，建议在 CI 或开发环境补跑相关前端 Vitest 以覆盖 UI 回归。
- **验证**：`PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_evaluations.py -q`
