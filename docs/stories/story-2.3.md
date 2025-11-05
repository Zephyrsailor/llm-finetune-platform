<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 2 的第三个故事要求在清洗完成后为数据科学家提供质量评估视图，覆盖困惑度、样本长度、重复率等指标，帮助判断数据是否满足微调要求。[来源: docs/epics.md:117-123]
- PRD 指出数据工作台需在清洗阶段后提供质量评分，并支持在控制台查看报告；该模块与清洗、格式转换共同构成“上传 → 清洗 → 评估 → 转换”的数据准备闭环。[来源: docs/PRD.md:32-35]
- 技术决策采用 Pandas/Polars + 内置规则引擎执行质量评估，指标与 artefact 目录需要可追溯、可导出，后续质量仪表要与训练/评估流水线兼容。[来源: docs/technical-decisions.md:16; docs/tech-specs/platform-core-modules.md:24-52]
- UX 流程 Flow1 明确清洗完成后进入“运行质量评估”步骤，仪表盘需支持 drill-down 以及配合异常样本处理，为 Story 2.4 的格式标准化提供输入值。[来源: docs/ux-specification.md:96-114]
- 合规与审计要求指标关联数据版本、保留导出报告，并记录审计日志，以便日后追踪质量问题或生成合规档案。[来源: docs/implementation-readiness-report-2025-10-28.md:79]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- Story 2.1/2.2 已落地数据导入与清洗逻辑，`dataset_versions.stats_json`、`data_cleaning_jobs` 与 artefact 目录可提供评估输入。本故事需沿用 `DataHubService` 分层与 Celery 任务模型，避免重复实现数据访问层。
- 已建立的 Dashboard 与 DatasetUpload UI 使用 TanStack Query + React Hook Form；新评估仪表需复用相同状态管理模式，确保缓存与权限逻辑一致。
- 现有 pytest fixture (SQLite + Celery eager) 已验证可用于数据管线测试；新增评估任务需在该基准上扩展，确保本地测试稳定运行。
- AuditLog 与 PermissionService 已在清洗功能中应用。本故事应延续 RBAC（`RoleOperation.DATA_IMPORT`/`EVALUATION_VIEW`）与审计事件记录，保持一致的安全模式。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 2.3: 数据质量评估仪表盘

Status: Done
<!-- story_header:end -->

## Story

作为数据科学家，  
我希望能够查看每个数据集版本的质量指标（困惑度、长度分布、重复率等）并定位异常样本，  
以便判断数据是否适合用于后续微调。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 清洗完成后自动触发质量评估任务，计算核心指标（困惑度/语言模型评分占位、样本长度统计、重复率、字段缺失率等），结果写入 `dataset_versions.stats_json` 并生成评估 artefact（summary/report），供仪表盘使用。[来源: docs/epics.md:117-123; docs/PRD.md:32-35]
2. 前端质量仪表盘可按工作空间 → 数据集 → 版本层级查看指标，支持 drill-down（列表显示异常样本或 TopN 问题数据），并展示评估建议；仅具备访问权限的成员可查看。[来源: docs/ux-specification.md:96-114]
3. 支持导出质量评估报告（JSON/CSV），并在导出时记录审计日志，报告需与具体数据版本关联，便于历史追溯与合规存档。[来源: docs/implementation-readiness-report-2025-10-28.md:79]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：扩展 `DataHubService` 与 Celery 任务，新增 `QualityEvaluationJob` 模型与任务逻辑，清洗后自动执行质量评估并写入指标、报告 artefact。（AC#1, AC#3）  
  - [x] 定义质量指标计算器（长度分布、重复率、缺失率、困惑度占位）、评估结果结构，更新 `dataset_versions.stats_json` 与 `quality_reports`（新表）并记录审计日志。（AC#1）  
  - [x] 提供 API：查询评估概要、异常样本、导出报告（JSON/CSV），并使用 RBAC 保护访问；补充 pytest 覆盖正常/失败流程。（AC#2, AC#3）
- [x] 前端：新增 `QualityDashboardPage`（位于 `frontend/src/app/data-hub`），展示评估指标与异常样本表格，支持切换工作空间/数据集/版本，并提供报告下载按钮。（AC#2, AC#3）  
  - [x] 扩展 `frontend/src/lib/api.ts`，封装评估相关 API；使用 TanStack Query 缓存数据，并显示加载、错误态。  
  - [x] 编写 Vitest/RTL 测试，覆盖指标渲染、异常列表、导出交互以及权限受限提示。（AC#2, AC#3）
- [x] DevOps/测试：丰富后端评估任务的 pytest fixture（包含生成示例数据、校验 artefact 整体性），确保质量评估对 SQLite/本地环境可运行；前端测试需 mock 下载行为以避免阻塞。（AC#1, AC#2）
- [x] 文档：更新 `docs/tech-specs/platform-core-modules.md`、`docs/ux-specification.md` 与 Story 文件，记录指标定义、评估流程、导出形式及权限要求；补充操作手册/FAQ 中的质量评估说明。（AC#1, AC#2, AC#3）
<!-- tasks_subtasks:end -->

## Dev Notes

- 质量评估基于清洗后的 `cleaned.jsonl` 等 artefact，建议采用 Pandas/Polars 单机实现，困惑度可使用语言模型评分占位（后续替换真实模型）。统计结果写入 `dataset_versions.stats_json.quality` 子字段，并在 artefact 中生成 `quality/summary.json`、`anomalies.csv`。
- 需要新增 `quality_evaluation_jobs`（或复用 `data_cleaning_jobs` 扩展）存储运行状态、指标摘要、日志路径；Celery 任务应与清洗任务串联，若清洗失败则跳过评估。
- 指标建议：行数（总/有效）、平均/中位长度、重复样本数、缺失字段计数、简易困惑度占位（可使用字典频率或调用内置小模型）。异常样本列表可储存在 artefact CSV，前端分页展示 TopN。
- 导出 API 需遵循 RBAC(`RoleOperation.DATA_IMPORT` or `EVALUATION_VIEW`) 并记录 `dataset.quality.export` 审计事件，与清洗导出逻辑保持一致。历史版本查看时需保证对象存储/本地 artefact 存在。
- 前端页面沿用深色主题，指标面板可复用 Dashboard 的卡片样式；drill-down 可使用表格或可折叠区域展示异常样本详情。下载按钮需提示文件大小及格式。
- 测试策略：后端通过构造小型示例数据（含重复/缺失值）验证指标；前端使用 Mock fetch/Blob 避免真实下载，确保交互顺畅。

### References

- docs/epics.md:117-123  
- docs/PRD.md:32-35  
- docs/ux-specification.md:96-114  
- docs/technical-decisions.md:16  
- docs/tech-specs/platform-core-modules.md:24-52  
- docs/implementation-readiness-report-2025-10-28.md:79

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-30 | 初始故事草稿 | Codex Agent |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-2.3.xml

### Agent Model Used

GPT-5 Codex（自动化代理）

### Debug Log References

- 2025-10-30 14:10 UTC 计划：
  1. 设计质量评估数据模型与 Celery 任务，扩展 Artefact 结构并落库 `quality_evaluation_jobs` 与 `quality_reports`。
  2. 实现后端评估 API（指标查询、异常样本、报告导出）及 pytest，确保与清洗流程串联。
  3. 搭建前端质量仪表（页面、API Hook、测试），更新文档与 Story 记录，准备一次性交付。
- 2025-10-30 15:20 UTC 实施：
  - 新增 `quality_evaluation_jobs` 模型、仓储与 Celery 任务，清洗完成后自动串联质量评估，生成 summary/anomalies artefact，并更新 `dataset_versions.stats_json.quality`。
  - 扩展 DataHub API（`quality/run`、`quality/summary`、`quality/export`），前端封装 `qualityApi`，实现 `QualityDashboardPage` 展示指标/异常、触发重新评估与导出；补充 Vitest 用例模拟下载。

### Completion Notes List

- 2025-10-30：实现质量评估管线，清洗后自动生成质量指标与报告，API/前端支持查看、重新评估与导出；pytest 全量通过。

### File List

- docs/stories/story-2.3.md
- docs/stories/story-context-2.3.xml
- backend/app/models/dataset.py
- backend/app/repositories/quality.py
- backend/app/services/data_hub.py
- backend/app/tasks/data_cleaning.py
- backend/app/api/datasets.py
- backend/app/schemas/datasets.py
- backend/tests/test_datasets.py
- backend/migrations/versions/0006_quality_evaluation.py
- frontend/src/lib/api.ts
- frontend/src/app/data-hub/QualityDashboardPage.tsx
- frontend/src/app/data-hub/QualityDashboardPage.test.tsx
