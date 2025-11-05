<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 4 的 Story 4.3 要求在评估结果基础上生成可视化报告，呈现指标对比与典型案例，供业务快速决策。[来源: docs/epics.md:243-251]
- PRD 的“评估与监控中心”明确报告需支持导出 PDF/Markdown，并与训练任务保持历史关联，满足交付与复盘需求。[来源: docs/PRD.md:50-76]
- UX 规格为 Evaluation Report 页面定义了指标对比图、提升/劣化案例区与导出操作，需在实现时完整覆盖布局与交互。[来源: docs/ux-specification.md:297-301]
- 架构映射指向 EvaluationRunner 与 ReportBuilder 组件，强调在现有评估域内完成报告生成和反馈能力，避免重复建设新域。[来源: docs/architecture.md:63-72]
- Brainstorming #3 优先级指出“标准化效果验证与报告交付”是客户价值关键，要求标准化模板与可视化输出支撑销售与业务沟通。[来源: docs/brainstorming-session-results-2025-10-23.md:105-109]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 现有 `backend/app/services/evaluation.py`、`backend/app/tasks/evaluation.py` 已落地自动评估与指标持久化，可在此基础上扩展报告聚合与导出逻辑，复用 `evaluation_jobs` artefact 结构。[来源: docs/tech-specs/platform-core-modules.md:95-101; backend/app/services/evaluation.py]
- `TrainingRun.metadata_json` 与实验管理（Story 3.5）已存储元数据，可用来建立训练运行、模型版本与报告的双向链接，避免新增表结构重复记录。[来源: docs/stories/story-3.5.md:7-120]
- 前端 `frontend/src/app/evaluation/EvaluationSuitePage.tsx` 与 `frontend/src/app/training/TrainingMonitorPage.tsx` 已消费评估任务与指标，新增报告详情页时应共用 TanStack Query 数据层并沿用现有权限与导航模式。[来源: frontend/src/app/evaluation/EvaluationSuitePage.tsx; frontend/src/app/training/TrainingMonitorPage.tsx]
- 导出能力可沿用 `GET /api/v1/evaluations/jobs/{id}/export` 接口，扩展 PDF 支持与分享链接时需复用现有权限 `evaluation_view` 与审计事件流水。[来源: backend/app/api/evaluation.py; docs/architecture.md:95-99]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 4.3: 报告生成与可视化

Status: Done
<!-- story_header:end -->

## Story

作为业务负责人，  
我希望在平台上获取包含指标对比与典型案例的评估报告，  
以便能够快速向干系人展示微调成效并指导后续决策。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 评估报告展示关键指标对比（如 BLEU/ROUGE-L/Exact Match/Perplexity）及可视化图表，结合至少一组典型提升样例与一组劣化样例，支持从评估 artefact 中跳转查看详情。[来源: docs/epics.md:243-251; docs/ux-specification.md:297-301]
2. 报告页面提供导出 Markdown、PDF 以及受控分享链接（带有效期/权限校验），导出内容包含指标图、案例列表与摘要说明。[来源: docs/PRD.md:50-53]
3. 报告与训练运行、模型版本互相可导航：从训练/部署视图可进入报告，报告中展示对应运行与模型版本信息，并在数据库内记录引用关系以供审计。[来源: docs/epics.md:243-251; docs/architecture.md:63-72]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端（AC#1, AC#3）：构建评估报告聚合与链接服务
  - [x] 扩展 `EvaluationService`/`ReportBuilder` 汇总指标对比、生成 Top/Bottom 示例数据结构，并落库或 artefact 供前端消费。[来源: docs/epics.md:243-251; docs/architecture.md:63-72]
  - [x] 在 `evaluation_jobs` 或附表中记录报告摘要与 `training_run_id`、`model_version_id` 映射，补充审计事件与元数据更新逻辑。[来源: docs/PRD.md:50-53; docs/stories/story-3.5.md:7-120]
- [x] 后端（AC#2）：完善导出与分享能力
  - [x] 扩展 `/api/v1/evaluations/jobs/{id}/export` 支持 Markdown→PDF 渲染，以及生成受限访问的分享链接（带签名、有效期）。[来源: docs/PRD.md:50-53]
  - [x] 记录导出与分享操作至审计日志，确保遵循 `evaluation_view` 权限与安全要求。[来源: docs/architecture.md:95-99]
- [x] 前端（AC#1）：实现 Evaluation Report 页面
  - [x] 新增报告详情路由，呈现指标卡片、图表和提升/劣化案例表格，遵循 UX 布局与可访问性要求。[来源: docs/ux-specification.md:297-301]
  - [x] 支持查看原始样例（如弹窗/侧栏展示），并从页面跳转至评估 artefact 或训练日志。
- [x] 前端（AC#2, AC#3）：导出操作与双向导航
  - [x] 在报告详情提供导出按钮、分享链接生成/复制操作，并反馈状态（成功/失败/权限不足）。
  - [x] 在训练监控、模型版本详情中增加“查看评估报告”入口，同时在报告页展示关联训练/模型信息与回链。
- [x] 测试与文档
  - [x] 补充后端 pytest 覆盖报告聚合、导出、链接写入与权限校验；前端新增 Vitest/RTL 用例验证页面渲染、导出交互与导航。[来源: docs/brainstorming-session-results-2025-10-23.md:105-109]
  - [x] 更新技术规格与 UX 文档，记录报告生成流程、导出策略与模板结构。
<!-- tasks_subtasks:end -->

## Dev Notes

- 报告生成应复用评估 artefact 目录（`/var/lib/llmft/{workspace}/{project|general}/evaluations/{job_id}`），在其中追加 `report.json/markdown` 结构，避免重复构建数据源。[来源: docs/tech-specs/platform-core-modules.md:95-101]
- 指标图表数据需与自动化评估结果保持同步，可直接读取 `evaluation_jobs.metrics_json`，并在报告聚合时写入 `baseline`/`delta` 等字段供前端可视化。[来源: backend/app/tasks/evaluation.py]
- 典型案例可基于评估输出中的样例得分或差异，若暂缺数据，可定义最小可行策略（例如选取提升/下降最大的若干条），并在文档中注明后续可替换为更精细算法。[来源: docs/brainstorming-session-results-2025-10-23.md:105-109]
- 分享链接应结合现有 RBAC：为每个链接生成一次性 token 与有效期，访问时仍需具备 `evaluation_view` 或特定分享权限，防止报告外泄。[来源: docs/PRD.md:50-53; docs/architecture.md:95-99]
- 需在前端使用现有 Chart 组件或引入 Recharts 统一风格，保持暗色主题兼容，并提供文本摘要以满足可访问性要求。[来源: docs/ux-specification.md:297-301]

### Project Structure Notes

- 后端建议在 `backend/app/services` 下新增 `evaluation_report.py` 或扩展现有 `evaluation.py`，同时在 `backend/app/api` 中暴露 `/evaluation/reports` 视图，遵循单体分层结构。[来源: docs/architecture.md:63-72]
- 可在数据库层新增轻量表/视图（如 `evaluation_reports`）或复用 `evaluation_jobs`，保持 Alembic 迁移与 SQLModel 一致；注意更新 `backend/app/schemas/evaluation.py`。[来源: docs/stories/story-3.5.md:7-120]
- 前端新增页面可置于 `frontend/src/app/evaluation/report`，共用 `lib/api.ts` 中的 API 客户端与 TanStack Query key，避免重复 fetch 逻辑。[来源: frontend/src/app/evaluation/EvaluationSuitePage.tsx]

### References

- docs/epics.md:243-251
- docs/PRD.md:50-76
- docs/ux-specification.md:297-301
- docs/architecture.md:63-99
- docs/brainstorming-session-results-2025-10-23.md:105-109
- docs/stories/story-3.5.md
- backend/app/services/evaluation.py
- backend/app/tasks/evaluation.py
- frontend/src/app/evaluation/EvaluationSuitePage.tsx
- frontend/src/app/training/TrainingMonitorPage.tsx

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 11:35 UTC 梳理 Story 4.3 验收标准，确认需补齐的报告聚合字段、审计链路与前端展示差距，确定“后端数据 → 前端呈现 → 文档/测试”执行顺序。
- 2025-10-31 12:20 UTC 扩展 `EvaluationService` 报告负载（训练/数据集上下文、分享令牌审计、PDF 生成修正），同步更新导出接口日志记录与 schema。
- 2025-10-31 13:05 UTC 更新 `EvaluationReportPage` 呈现训练/数据集信息与导出反馈，调整 Vitest 用例；执行 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_evaluations.py -q` 验证导出与分享链路，完成文档更新。

### Completion Notes List

- 后端补齐评估报告聚合：返回训练运行、项目、数据版本与 artefact 链接，分享令牌改为字符串 subject 并新增访问/导出审计事件，PDF 导出兼容 ASCII。
- 前端报告页整合指标卡、阈值校验、案例列表与训练/数据集信息卡片，导出/分享操作提供复制反馈与异常提示。
- 更新 `frontend/src/lib/api.ts`、`EvaluationReportPage.test.tsx` 以适配新 payload；文档补充报告生成与交互说明。
- 运行 `backend/tests/test_evaluations.py` 覆盖 Markdown/JSON/PDF 导出与分享流程，遵照用户限制未执行全量 Vitest。

### File List

- backend/app/services/evaluation.py
- backend/app/api/evaluation.py
- backend/app/schemas/evaluation.py
- frontend/src/lib/api.ts
- frontend/src/app/evaluation/EvaluationReportPage.tsx
- frontend/src/app/evaluation/EvaluationReportPage.test.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
- docs/stories/story-4.3.md

### Change Log

- 2025-10-31 13:20 UTC 完成 Story 4.3 报告生成与可视化实现：后端聚合/导出/审计链路、前端报告页与文档更新。
