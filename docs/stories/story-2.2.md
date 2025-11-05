<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 2 要求在数据导入后提供可配置的清洗与脱敏流水线，合规负责人可以按数据集切换规则模板，保障去重、噪声过滤与 PII 处理的可控性。[来源: docs/epics.md:110-118; docs/PRD.md:32-35]
- 架构层面将 DataHubService 作为清洗管道的核心服务，结合 DataPipelineOrchestrator、Celery 任务与 artefact 目录 `/var/lib/llmft/datasets/{workspace}/{dataset_id}/v{n}`，每次运行需生成版本化快照和可审计日志。[来源: docs/architecture.md:60-104; docs/tech-specs/platform-core-modules.md:28-44]
- 技术栈预期使用 Pandas/Polars 与内置规则引擎执行脱敏/统计，同时保持与后续数据质量仪表盘、格式标准化故事的接口兼容，因此要落地标准化的 `stats_json` 与导出能力。[来源: docs/PRD.md:139-140; docs/tech-specs/platform-core-modules.md:28-44]
- UX 流程强调“上传 → 清洗/脱敏 → 查看质量评估”，本故事需补齐第二步：提供规则模板管理、运行状态可视化与清洗结果指标，为故事 2.3 的质量仪表盘提供输入。[来源: docs/ux-specification.md:96-114]
- 未发现独立的技术规格文档（`tech-spec-epic-2*.md`），后续实现需同步补充技术说明，避免与架构设计脱节。
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- Story 2.1 已交付数据集导入、版本登记与清洗任务骨架，当前 Celery 任务默认同步执行并写入日志，后续需扩展为实际的规则执行与指标更新；调度层继续复用 `DataHubService` + Repository + Celery 的分层模式，并遵循项目 Python 编码规范。[来源: docs/stories/story-2.1.md; docs/Python编码规范与风格指南.md]
- artefact 目录与 Data Version Snapshot 模式已在架构/技术规格中定义，本故事新增的清洗产物（clean 目录、统计报告、导出文件）必须放在既定路径下，并更新 `stats_json` 和 `data_cleaning_jobs` 记录以供仪表盘与审计使用。[来源: docs/architecture.md:98-104; docs/tech-specs/platform-core-modules.md:28-44]
- 需要补齐 Story 2.1 QA 遗留的测试脚本（SQLite 表初始化）与前端断言差异，确保新清洗功能的测试可以在本地持续集成环境中稳定运行。
- Celery/Redis 仍为默认调度组件；在扩展清洗逻辑时必须保持任务幂等（重复运行不会污染 artefact），并记录告警/错误日志供治理模块消费。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 2.2: 数据清洗与脱敏流水线

Status: Done
<!-- story_header:end -->

## Story

作为合规负责人，  
我希望能够配置去重、噪声过滤与敏感词/PII 脱敏策略并查看运行结果，  
以便在数据用于训练前确保满足企业安全与合规要求。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 支持创建/维护清洗规则模板（包含去重、噪声过滤、PII/敏感词脱敏等步骤），并能对每个数据集版本选择启用或禁用具体模板，调用时必须记录使用的规则版本。[来源: docs/epics.md:110-118; docs/architecture.md:60-104]
2. 每次清洗生成的 `dataset_versions.stats_json` 与清洗任务日志需包含关键指标（去重后条目数、脱敏字段计数、失败记录/样本路径、耗时等），前端可在完成提示中展示，后端提供查询接口。[来源: docs/tech-specs/platform-core-modules.md:28-44]
3. 清洗与脱敏规则、以及本次运行使用的模板和结果摘要可导出（JSON 或 CSV），供审计与合规留档，导出文件路径与下载接口需受 RBAC 权限保护。[来源: docs/epics.md:110-118; docs/PRD.md:32-35]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：在 `backend/app/models` / `repositories` / `services` 中新增清洗规则模板与执行配置模型，提供 CRUD 与 dataset-version 绑定 API；为 `DataHubService` 增加选择模板并触发清洗的入口。（AC#1）
  - [x] 设计规则模板结构（含步骤顺序、参数、脱敏词典引用等）并落库，提供 `POST /api/v1/datasets/cleaning/templates`、`/cleaning/assignment` 等接口；补充测试覆盖模板启用/禁用与权限校验。（AC#1）
- [x] 后端：扩展 `data_cleaning.run_initial_cleaning` Celery 任务，流水执行选中模板（Pandas/Polars 规则），写入 `stats_json`、日志和 artefact（clean 目录），并提供导出接口。（AC#2, AC#3）
  - [x] 在清洗完成后记录指标（总行数、去重删除、脱敏字段计数、错误明细），更新 `DataCleaningJob` 状态与 `logs_path`；实现结果导出（JSON/CSV）并受 RBAC 保护。（AC#2, AC#3）
- [x] 前端：在 `frontend/src/app/data-hub` 下新增清洗配置与执行页面/面板，可选择规则模板、触发清洗并查看统计与导出链接。（AC#1, AC#2, AC#3）
  - [x] 使用 React Hook Form + TanStack Query 实现模板管理、运行状态提示和指标展示；提供导出按钮并以 Vitest/RTL 覆盖交互。（AC#2, AC#3）
- [x] DevOps/测试：完善后端 pytest fixture，确保 SQLite/临时数据库会自动建表；新增清洗执行、指标统计与导出相关测试；前端 Vitest 覆盖模板渲染、状态提示与导出按钮交互。（AC#1, AC#2, AC#3）
- [x] 文档：在 `docs/tech-specs/platform-core-modules.md` / `docs/ux-specification.md` 描述清洗流水线设计、指标字段与导出流程，并在 Story 2.1 QA 说明中关闭遗留测试注意事项；同步更新架构文档 DataHub 小节。（AC#1, AC#2, AC#3）
<!-- tasks_subtasks:end -->

## Dev Notes

- 清洗与脱敏执行以 Pandas/Polars + 规则引擎为基础，需要提供可扩展的步骤模型（去重、噪声过滤、PII 替换），并支持多模板并存；规则参数建议序列化为 JSON，便于导出与版本化。[来源: docs/PRD.md:139-140; docs/epics.md:110-118]
- 清洗任务运行在 Celery（当前 `task_always_eager` 同步执行）上，完成后应更新 `dataset_versions.stats_json` 与 `data_cleaning_jobs`，同时将清洗产物写入 `datasets/{dataset_id}/v{n}/clean`（按步骤划分子目录）。任务需幂等、可重跑，并将失败记录落日志供治理模块消费。[来源: docs/tech-specs/platform-core-modules.md:28-44]
- 清洗结果导出需遵循 RBAC 权限（`data_import`/`approval_manage`），同时记录审计日志 `dataset.cleaning.export`，导出文件放置在 artefact 目录并在一定周期自动清理，避免敏感数据长期保存。[来源: docs/architecture.md:60-104; docs/PRD.md:32-35]
- Story 2.1 留下的测试补缺（SQLite 建表、前端中文断言）需要在本故事中补齐，否则 QA 将难以自动验证清洗流水线；完成后请同步更新 `docs/stories/story-2.1.md` 的已知问题或在 QA 交付说明中关闭该项。

### Project Structure Notes

- 后端规则模板与执行逻辑建议置于 `backend/app/services/data_cleaning.py`（或扩展 `DataHubService`），模型可放在 `backend/app/models/dataset.py` 同文件或独立模块；Celery 任务追加到 `backend/app/tasks/data_cleaning.py` 并配置队列。
- 新增 API 路由放入 `backend/app/api/datasets_cleaning.py`（或扩展既有 `datasets.py`），并在 `backend/app/api/router.py` 注册；与 RBAC 结合需复用 `PermissionService.require_operation(workspace_id, RoleOperation.DATA_IMPORT)`.
- 前端新增页面位于 `frontend/src/app/data-hub/`（如 `CleaningPipelinePage.tsx`），相关 API 调用封装在 `frontend/src/lib/api.ts`，必要时拆分 hooks(`useCleaningTemplates`)。
- 清洗导出文件可使用命名 `cleaning-results/{dataset_version_id}/summary.json` 等，并在 docs 中注明路径与清理策略。

### References

- docs/epics.md:110-118  
- docs/PRD.md:32-35,139-140  
- docs/architecture.md:60-104  
- docs/tech-specs/platform-core-modules.md:28-44  
- docs/ux-specification.md:96-114  
- docs/stories/story-2.1.md

## Change Log

| 日期 | 说明 | 作者 |
| ---- | ---- | ---- |
| 2025-10-31 | 初始草稿 | Codex Agent |

## Dev Agent Record

### Context Reference
- docs/stories/story-context-2.2.xml

### Agent Model Used

（待补充）

### Debug Log References

- 2025-10-30 12:05 UTC 计划：
  1. 定义清洗规则模板的数据模型与 API（模板 CRUD、dataset-version 绑定），补齐权限校验与测试。
  2. 扩展 `run_initial_cleaning` 执行实际规则：落地去重/脱敏示例、统计指标写入 `stats_json` 与 artefact、记录导出文件。
  3. 新增导出与查询接口（获取统计、下载结果），补文档说明；同时修复 Story 2.1 遗留的 SQLite fixture 问题支撑测试。
- 2025-10-30 13:40 UTC 实施：
  - 新增清洗模板/绑定模型与仓储，提供模板 CRUD、dataset 分配与 Celery 任务模板快照。
  - 扩展 `DataHubService` 与 `run_initial_cleaning`，执行去重/脱敏/噪声过滤，生成统计、summary.json 与 JSONL/CSV 导出，并记录审计事件。
  - 新增 API 路由 `/v1/datasets/cleaning/*` 及导出端点，更新 pytest 覆盖模板管理、清洗执行与导出。

### Completion Notes List

- （待补充）

### File List

- docs/stories/story-2.2.md
