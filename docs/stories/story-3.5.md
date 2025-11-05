<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 3 的 Story 3.5 聚焦“元数据与实验管理”，要求记录训练任务的模型/数据/参数/耗时等元数据，在界面中比较多次实验差异，并支持导出到知识库或 BI 工具。[来源: docs/epics.md:198-206]
- PRD 在“微调执行引擎”要求保存完整的训练元数据（模型版本、数据版本、参数、日志），并支持多源数据导入时记录来源，为后续审计与复盘提供依据。[来源: docs/PRD.md:33-44]
- 平台核心技术规格已定义 `training_jobs`、`training_runs`、`training_metric_samples` 等模型与 API，需要在此基础上扩展元数据字段、比对接口及导出能力，保持与现有仓储/服务分层一致。[来源: docs/tech-specs/platform-core-modules.md:56-113]
- 架构文档描述训练模块采用 FastAPI + Celery + PostgreSQL 的单体架构，artefact 与日志落地 `/var/lib/llmft/training/{workspace}/{project}/runs/{run_id}`，需在该目录组织实验快照与对比数据，并复用既有审计/日志机制。[来源: docs/architecture.md:5-136]
- 产品简报强调需要沉淀最佳实践与实验结果至知识库，形成可复用模板和行业案例，为后续治理协作与知识沉淀能力打基础。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:95-120]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 现有 TrainingService 采用 Repository 模式管理 `training_jobs`/`training_runs`，需在服务层新增元数据聚合、对比与导出接口，并保持与审计日志、快照/监控模块（Story 3.3、3.4）一致的生命周期管理。[来源: docs/tech-specs/platform-core-modules.md:56-113; docs/stories/story-3.4.md]
- artefact 目录 `/var/lib/llmft/training/...` 已存储模型快照与指标，本故事应在同层级维护 `metadata.json`、对比报告或导出文件，并复用 runtime 脚本的清理/保留策略，避免堆积与误删。[来源: docs/tech-specs/runtime-operations.md:20-120]
- 前端 Training 模块已具备模板库、向导、监控、快照导航，可在 `frontend/src/app/training` 新增“实验对比”页面，沿用 TanStack Query/Tailwind 组件，实现差异视图与导出操作，与 UX 的对比可视需求保持一致。[来源: docs/ux-specification.md:280-316]
- 知识库/治理能力将在 Epic 6 扩展，导出结果需留出 API/格式（如 JSON/Markdown）供后续知识库与 BI 工具调用，并使用审计日志标记导出事件，满足合规要求。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:95-120; docs/epics.md:262-370]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 3.5: 元数据与实验管理

Status: Done
<!-- story_header:end -->

## Story

作为产品分析师，  
我希望追踪训练元数据并对比实验结果，  
以便沉淀最佳实践并快速复盘/优化。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 训练任务记录模型版本、数据版本、超参、耗时、资源消耗/成本等元数据（含日志/审计引用），并可在后端 API 查询与导出。[来源: docs/epics.md:198-206; docs/PRD.md:33-44]
2. 平台 UI 支持选择两次训练运行，展示指标与配置差异（含可视化对比、快照链接、告警记录），便于分析实验效果。[来源: docs/epics.md:198-205; docs/ux-specification.md:280-316]
3. 元数据与对比结果可导出为结构化文件（JSON/CSV/Markdown），通过知识库/BI 占位接口留痕（含审计日志），支持后续治理与汇报。[来源: docs/epics.md:204-206; docs/product-brief-llm-finetune-platform-2025-10-23.md:95-120]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端（AC#1）：扩展 `training_runs`/`training_jobs` 元数据模型与仓储，记录模型/数据版本、参数、耗时、资源/成本，并暴露查询与分页 API。
  - [x] 在 `TrainingService` 执行流程中聚合训练上下文（模板、数据格式、快照、监控告警）写入 `metadata_json`，并新增审计事件 `training.experiment.recorded`。
  - [x] 针对元数据新增验证/迁移（Alembic）、容错处理与 pytest 覆盖（字段写入、查询、导出）。
- [x] 后端（AC#2）：实现训练运行对比 API，返回指标差异、配置 diff、相关快照/告警链接，并可按工作空间筛选。
  - [x] Reuse `training_metric_samples` 计算对比数据，落地临时报告（JSON），并扩展监控/快照链接字段。
- [x] 后端（AC#3）：实现导出/知识库占位接口，生成 JSON/CSV/Markdown，并写入审计日志 + 导出 artefact（含 retention 策略）。
- [x] 前端（AC#2, AC#3）：在 Training 模块新增“实验管理/对比”页面，提供运行筛选、差异对比视图、导出按钮与知识库占位操作。
  - [x] 扩展 `frontend/src/lib/api.ts` 调用新 API，提供 TanStack Query 缓存与错误提示，支持响应式布局。
- [x] 测试与文档（AC#1-#3）：补充后端 pytest（元数据写入、对比、导出），前端单测/交互测试（对比渲染、导出回调），并更新技术规格/架构/UX 文档说明元数据目录、API 契约与导出策略。
<!-- tasks_subtasks:end -->

## Dev Notes

- 元数据字段建议扩展 `training_runs.metadata_json`（模型、数据、超参、GPU/耗时/成本、快照引用、告警 ID），并保留扩展空间；对比 API 需返回指标差异、配置 diff、链接至日志/快照/评估报告。[来源: docs/epics.md:198-206; docs/tech-specs/platform-core-modules.md:56-113]
- Artefact 目录可新增 `metadata.json`、`comparison-{run_a}-{run_b}.md` 等文件，遵循 runtime 脚本清理策略，并在导出时将文件同步到知识库占位目录或返回下载链接。[来源: docs/tech-specs/runtime-operations.md:20-120]
- 导出与知识库占位需记录审计事件（例如 `training.experiment.exported`），并预留后续 Epic 6 的知识库 API 接口（可配置导出目标、标签、描述）。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:95-120]
- 前端对比页面可复用监控/快照页面的卡片与图表组件，支持参数差异表（高亮变化值）、指标折线/雷达图、评论占位；导出后提示链接或在通知中心补充后续操作。[来源: docs/ux-specification.md:280-316]
- 需确保 RBAC：仅具备 `training_launch` 或 `approval_manage` 的成员可查看/导出实验详情，导出时强调敏感信息脱敏（如 API Key、访问 Token）。[来源: docs/PRD.md:33-44; docs/tech-specs/platform-core-modules.md:56-113]

### Project Structure Notes

- 后端改动集中于 `backend/app/services/training.py`、`backend/app/repositories/training.py`、`backend/app/api/training.py`，需配合新增 Alembic 迁移与测试目录 `backend/tests/test_training_experiments.py`。
- 前端新增页面建议放置在 `frontend/src/app/training`（例如 `TrainingExperimentsPage.tsx`）并扩展导航 `TrainingNav.tsx`、API 客户端 `frontend/src/lib/api.ts`、测试 `frontend/src/app/training/TrainingExperimentsPage.test.tsx`。
- 文档需同步更新 `docs/tech-specs/platform-core-modules.md` 与 `docs/ux-specification.md`，并在故事完成后于知识库/治理相关文档记录导出策略。

### References

- docs/epics.md:198-206 – Epic 3 Story 3.5 验收标准与先决条件  
- docs/PRD.md:33-44 – 微调执行引擎对元数据留存与日志追溯的要求  
- docs/tech-specs/platform-core-modules.md:56-113 – TrainingService 数据模型、API 与审计策略  
- docs/architecture.md:5-136 – 平台整体架构、训练模块组件与 artefact 布局  
- docs/tech-specs/runtime-operations.md:20-120 – 训练 artefact 管理与清理脚本示例  
- docs/product-brief-llm-finetune-platform-2025-10-23.md:95-120 – 知识库沉淀与行业模板蓝图  
- docs/ux-specification.md:280-316 – 训练对比/报告关键布局与导出交互

## Dev Agent Record

### Context Reference

- docs/stories/story-context-3.5.xml

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 10:25 UTC 审阅现有训练服务/监控/快照实现，确认需在 `training_runs` 扩展 `metadata_json`，新增实验管理服务与 API（列表/对比/导出），并引入前端实验页面复用监控/快照筛选机制。
- 2025-10-31 11:10 UTC 梳理 Story 3.5 AC，规划实现步骤：① 建立 `TrainingExperimentService` 负责元数据聚合、对比与导出；② 更新 Celery 训练任务写入结构化元数据并添加 Alembic 迁移；③ 提供 `/v1/training/experiments` 系列 API 与权限校验；④ 构建前端“实验管理/对比”页面与导出交互，补充 pytest/Vitest 测试与技术文档。

### Completion Notes List

- 聚合训练元数据、对比与导出能力已经串联：Celery 任务回填 `metadata_json`，`/v1/training/experiments` 系列 API 提供列表、详情、对比、导出；前端新增“实验管理/对比”页面支持筛选、查看详情、导出报告，并补齐后端 pytest 与前端 Vitest 断言，同时更新技术规格及 UX 组件说明。

### File List

- backend/app/services/training_experiments.py
- backend/app/services/errors.py
- backend/app/repositories/training.py
- backend/app/tasks/training.py
- backend/app/schemas/training_experiments.py
- backend/app/api/training_experiments.py
- backend/app/api/deps.py
- backend/app/api/router.py
- backend/tests/test_training_experiments.py
- backend/migrations/versions/0013_training_run_metadata.py
- frontend/src/lib/api.ts
- frontend/src/app/router.tsx
- frontend/src/app/training/TrainingNav.tsx
- frontend/src/app/training/TrainingExperimentsPage.tsx
- frontend/src/app/training/TrainingExperimentsPage.test.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md

### Change Log

- 2025-10-31 11:55 UTC 建立训练实验管理后端服务与 API，前端新增实验对比页面，并同步补充测试与文档说明。
