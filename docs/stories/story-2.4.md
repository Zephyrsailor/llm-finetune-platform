<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 2 的下一步目标是将清洗与质量评估后的数据标准化输出，支持 JSONL/SFT/Parquet 等格式版本化管理，确保训练模块可以直接消费。[来源: docs/epics.md:124-132]
- PRD 指出数据工作台需提供格式转换、版本编号与校验和，同时允许下载及回滚历史版本，便于不同训练策略复用数据。[来源: docs/PRD.md:32-35]
- 架构层面 Artefact 目录需保持 `/var/lib/llmft/datasets/{workspace}/{dataset_id}/v{n}/` 结构，格式转换结果应生成独立子目录并记录元信息，以便训练流水线引用。[来源: docs/architecture.md:60-104]
- 现有 DataHubService、Celery 任务和清洗/评估流程已建立，格式标准化需要沿用该分层并与质量评估结果建立依赖关系（例如仅对质量达标版本允许转换）。
- 权限和审计要求与之前故事一致：导出文件需受 RBAC 保护，并在导出、回滚时写入审计日志。
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- Story 2.1/2.2/2.3 已落地数据导入、清洗、质量评估，`dataset_versions`、`quality_evaluation_jobs` 等结构可扩展以记录格式转换状态与 Artefact；需避免重复模型定义。
- 已有 Celery 任务模式（清洗、质量评估）可复用，转换任务应幂等并在 Artefact 目录生成标准化文件，记录版本元数据（checksum、格式列表）。
- 前端现有 Data Hub Pages（上传、清洗、质量）已使用 TanStack Query 和 Tailwind 组件，新页面应延续此结构，提供版本列表、转换状态与下载能力。
- Tests/fixtures：Story 2.2 已修复 SQLite/Celery eager 环境，可直接构造示例数据并断言生成的标准化文件与元信息。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 2.4: 格式标准化与版本管理

Status: Done
<!-- story_header:end -->

## Story

作为 ML 工程师，  
我希望可以将清洗并通过质量评估的数据转换为标准格式（JSONL/SFT/Parquet等）并管理版本，  
以便训练流水线可以直接引用指定版本的数据进行微调。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 清洗+质量评估完成后，可触发格式转换任务生成指定格式文件（至少 JSONL/SFT/Parquet 占位实现），输出文件带有版本号、校验和并记录在数据库/Artefact 中。[来源: docs/epics.md:124-132; docs/PRD.md:32-35]
2. 平台提供版本管理接口：列出所有数据集版本及可用格式，支持下载、删除/回滚、查看校验和；操作需遵循 RBAC 并记录审计日志。[来源: docs/epics.md:124-132]
3. 前端 Data Hub 页面展示格式转换状态与可下载链接，可触发重新转换/回滚并提示风险，同时与现有流程（上传→清洗→评估→转换）连贯。[来源: docs/ux-specification.md:96-114]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：扩展 `DataHubService`，新增格式转换 Celery 任务（`run_format_standardization`），记录 `dataset_format_versions` 模型（格式类型、校验和、路径、状态）并更新 `dataset_versions` 元数据。[来源: backend/app/services/data_hub.py; backend/app/tasks/data_cleaning.py; backend/app/models/dataset.py]（AC#1）
  - [x] 提供 API：触发转换、列出可用格式、下载、激活/回滚；仅允许清洗质量完成的版本执行转换，并写入审计日志。[来源: backend/app/api/datasets.py; backend/app/schemas/datasets.py]（AC#1, AC#2）
- [x] 前端：新增“格式标准化”页面，展示转换状态、校验和、下载链接、激活/重新转换等操作，使用 TanStack Query 管理数据流。[来源: frontend/src/app/data-hub/FormatStandardPage.tsx]（AC#3）
- [x] 测试：后端 pytest 覆盖格式转换流程（多格式输出、校验和、激活切换），前端 Vitest 覆盖界面渲染与交互；Celery eager + SQLite 环境稳定运行。[来源: backend/tests/test_datasets.py; frontend/src/app/data-hub/FormatStandardPage.test.tsx]（AC#1, AC#2, AC#3）
- [x] 文档：更新技术规格、UX 说明与 Story 记录，补充格式转换产物路径与回滚策略说明。[来源: docs/tech-specs/platform-core-modules.md; docs/ux-specification.md]（AC#1, AC#2, AC#3）
<!-- tasks_subtasks:end -->

## Dev Notes

- 格式转换通过 Celery 任务 `run_format_standardization` 在 `/standard/{fmt}/` 子目录输出 JSONL/SFT/Parquet 文件，并计算 SHA256 校验和。[来源: backend/app/tasks/data_cleaning.py]
- `dataset_format_versions` 记录格式类型、路径、校验和、状态与激活标记，支持历史版本并在 `DatasetVersion.stats_json` 中同步摘要。[来源: backend/app/models/dataset.py; backend/app/services/data_hub.py]
- 仅当清洗和质量评估完成时才允许触发转换；重复执行会生成新版本并保留旧版本供激活/回滚使用。[来源: backend/app/services/data_hub.py]
- 前端 `FormatStandardPage` 展示格式状态、校验和、文件大小与更新时间，并提供重新转换、激活、下载等操作。[来源: frontend/src/app/data-hub/FormatStandardPage.tsx]
- 导出、激活等操作写入审计日志并受 `RoleOperation.DATA_IMPORT` 权限控制；错误场景会在前端提示。[来源: backend/app/api/datasets.py]

### References

- docs/epics.md:124-132  
- docs/PRD.md:32-35  
- docs/architecture.md:60-104  
- docs/ux-specification.md:96-114  
- docs/technical-decisions.md:16

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-30 | 初始草稿 | Codex Agent |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-2.4.xml

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-30 15:40 UTC 计划：
  1. 设计 `dataset_format_versions` 模型与格式转换 Celery 任务，占位生成 JSONL/SFT/Parquet 文件并记录校验和。
  2. 实现后端 API（触发转换、列表、下载、回滚）及 pytest；更新审计日志。
  3. 构建前端格式管理界面、封装 API 与测试，更新文档并准备交付。
- 2025-10-30 17:20 UTC 实施：新增 `dataset_format_versions` 模型日志字段、补齐 Celery 任务幂等与激活流程，扩展 FastAPI 路由/Schema，并生成迁移 `0007_format_versions.py`；执行 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_datasets.py -q` 全量通过。

### Completion Notes List

- 2025-10-30：完成格式转换任务、版本管理 API 及前端界面，迁移与文档同步更新。
- 2025-10-31：在本地复跑 `backend/tests/test_datasets.py` 与 `FormatStandardPage.test.tsx`，验证转换触发、激活与下载流程稳定。

### File List

- docs/stories/story-2.4.md
- backend/app/models/dataset.py
- backend/app/repositories/format.py
- backend/app/services/data_hub.py
- backend/app/api/datasets.py
- backend/app/schemas/datasets.py
- backend/migrations/versions/0007_format_versions.py
- backend/tests/test_datasets.py
