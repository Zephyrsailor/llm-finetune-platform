<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 4 的 Story 4.4 要求在评估报告中沉淀业务反馈、TODO 与改进指标，以支撑持续复盘和后续训练目标设定。[来源: docs/epics.md:255-263]
- PRD 的“评估与监控中心”与“治理与协作”章节强调报告需提供人工反馈入口、历史记录与多团队协作能力，保证业务方能跟踪决策依据。[来源: docs/PRD.md:50-58]
- UX 站点地图将 Evaluation 模块拆分出“反馈与备注”页签，并突出协作可视化、评论与审批机制，满足业务产品经理的沟通诉求。[来源: docs/ux-specification.md:17-38,65-77]
- 架构映射将 FeedbackService 作为评估域核心组件之一，需与现有 EvaluationRunner、ReportBuilder 协作，并与 KnowledgeBaseService 对接复盘数据。[来源: docs/architecture.md:63-72]
- 产品简报将“知识库建设、沉淀最佳实践”列为战略举措，要求平台将反馈、经验和指标纳入可查询的知识库或模板库。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:93-138]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- 当前 `EvaluationService` / `EvaluationReportPage` 已完成指标与报告展示（Story 4.3），本故事需在同一 API/UI 层扩展评论、TODO、业务指标记录，同时沿用 TanStack Query、审计日志与 artefact 目录结构。[来源: backend/app/services/evaluation.py; frontend/src/app/evaluation/EvaluationReportPage.tsx]
- `TrainingRun.metadata_json` 与实验管理（Story 3.5）已支持导出到知识库，占位接口可复用为反馈记录的持久化与查询基础，避免重复构建数据通道。[来源: docs/stories/story-3.5.md:1-116]
- 架构侧已有 KnowledgeBaseService（Epic 6），需要在当前阶段以“知识库占位”方式写入复盘内容，保持与后续治理协作故事的兼容性。[来源: docs/architecture.md:63-72]
- UX 组件库定义了“评估报告卡片支持评论&TOD O”，前端应沿用现有卡片/侧栏模式，确保暗色主题与可访问性一致性。[来源: docs/ux-specification.md:171-184]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 4.4: 反馈与复盘记录

Status: Done
<!-- story_header:end -->

## Story

作为产品经理，  
我希望在评估报告中记录业务反馈与改进建议，  
以便后续迭代能够追踪决策依据并持续优化模型效果。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 评估报告详情页支持评论、标注 TODO、附加业务指标，并与原始报告内容关联展示。[来源: docs/epics.md:260-262; docs/ux-specification.md:171-184]
2. 反馈记录可同步到知识库占位（含项目/模型标签），支持按工作空间与项目查询下载，形成可追踪的复盘沉淀。[来源: docs/epics.md:262; docs/product-brief-llm-finetune-platform-2025-10-23.md:93-138]
3. 创建新训练任务时，可引用历史反馈（目标/风险/待改进项）作为配置建议或必填检查项，确保复盘信息进入迭代循环。[来源: docs/epics.md:263; docs/PRD.md:50-58]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端（AC#1, AC#2）：扩展评估域服务与数据模型
  - [x] 在 `EvaluationService` / `FeedbackService` 中新增反馈实体（评论、TODO、业务指标、自定义标签），持久化至数据库并与 `evaluation_jobs`、`training_runs` 关联。[来源: docs/architecture.md:63-72]
  - [x] 暴露 CRUD 与查询 API：支持按工作空间、项目、报告、作者、标签过滤；列表接口需分页与权限校验，写入审计日志（create/update/delete）。[来源: docs/PRD.md:55-58]
  - [x] 实现知识库同步占位：将反馈导出为 Markdown/JSON 并写入 `/var/lib/llmft/knowledge/{workspace}/{project}/feedback/`，记录 `evaluation.feedback.exported` 审计事件供后续 KnowledgeBaseService 消费。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:93-138; docs/stories/story-3.5.md:40-116]
- [x] 后端（AC#3）：训练配置引用反馈
  - [x] 在 `TrainingService` 创建/克隆任务流程中增加“引用历史反馈”步骤：根据项目/模型推荐待改进项并写入 `training_jobs.params_json` 或 Notes 字段。[来源: docs/epics.md:263]
  - [x] 提供 API 返回近期反馈摘要（目标、风险、指标阈值），并于创建任务时校验“待改进项是否已处理”。
- [x] 前端（AC#1, AC#2）：Evaluation 模块 UI
  - [x] 在 `EvaluationReportPage` 增加评论/TODO 面板（支持 Markdown、@指派、状态切换），同步展示业务指标及知识库导出按钮，遵循浅/深色主题与无障碍要求。[来源: docs/ux-specification.md:17-38,171-184]
  - [x] 实现反馈列表与筛选（按标签、负责人、状态），并提供导出/复制链接能力，前端调用知识库占位 API。
  - [x] 为训练向导、训练监控页面添加“引用反馈”提示与弹窗，支持一键填充改进目标或生成 TODO。
- [x] 测试与文档
- [x] 编写后端 pytest（API 权限、评论/TODO 流程、知识库导出、训练引用校验）与数据库迁移测试。
- [x] 增补前端 Vitest/RTL 用例覆盖评论交互、TODO 状态切换、反馈引用流程；记录在文档/Story 完成笔记。
- [x] 更新 `docs/tech-specs/platform-core-modules.md` 与 `docs/ux-specification.md`，描述 FeedbackService 模块、知识库同步策略与 UI 流程。
- [x] [AI-Review][High] 修复 `backend/app/repositories/evaluation.py` 中 `EvaluationFeedbackRepository.update` 被同名方法覆盖，导致反馈更新接口抛出 TypeError 并阻断 TODO/指派操作。
<!-- tasks_subtasks:end -->

## Dev Notes

- 反馈数据需与评估 artefact 目录解耦：业务附件（如截图、文档）可落地 `evaluations/{job_id}/feedback/{feedback_id}`，但结构化评论、TODO、指标应存数据库并关联审计事件，防止文件系统成为唯一真相。[来源: docs/architecture.md:63-72]
- 知识库占位导出格式推荐包含：项目、评估任务、训练运行、标签、评论摘要、指标快照、创建/更新时间，符合后续 KnowledgeBaseService 读取格式；导出文件需遵循 retention 策略，避免无限增长。[来源: docs/stories/story-3.5.md:40-116]
- 引用反馈到训练任务时，应在 UI 中提示“来自报告 #ID, 创建人, 时间”，并允许标记“已处理”写回反馈条目，形成闭环；必要时同步通知或审批流（与 Epic 6 故事兼容）。[来源: docs/ux-specification.md:17-38,171-184]
- 审计与权限：评论/反馈操作遵循 `evaluation_view` + `evaluation_manage` 权限，导出/知识库同步需追加 `governance_manage` 或工作空间管理员限制，满足治理要求。[来源: docs/PRD.md:55-58; docs/architecture.md:63-72]

### Project Structure Notes

- 后端：建议在 `backend/app/models/evaluation.py` 新增 `EvaluationFeedback` 模型，配套 `EvaluationFeedbackRepository`、`FeedbackService`，并在 `backend/app/api/evaluation.py` / `router.py` 暴露 `/evaluations/feedback` 子路由。
- 前端：新增 `frontend/src/app/evaluation/FeedbackPanel.tsx`、`frontend/src/app/evaluation/hooks/useFeedback.ts`，共用 TanStack Query key，与 Trainning Wizard 页面共享引用组件。
- 知识库占位脚本可暂放 `backend/app/services/knowledge_base.py`（轻量），后续 Epic 6 可迁移至治理模块。

### References

- docs/epics.md:255-263
- docs/PRD.md:50-58
- docs/ux-specification.md:17-38,65-77,171-184
- docs/architecture.md:63-72
- docs/product-brief-llm-finetune-platform-2025-10-23.md:93-138
- docs/stories/story-3.5.md:1-116
- backend/app/services/evaluation.py
- frontend/src/app/evaluation/EvaluationReportPage.tsx

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- 2025-10-31 14:10 UTC 查询 epic/PRD/UX/架构资料，确定反馈、知识库、训练引用三大需求面向。
- 2025-10-31 14:40 UTC 评估现有 EvaluationService/Report 页面结构，引出需扩展的 API、前端组件与审计策略。
- 2025-10-31 14:55 UTC 整理实施任务清单与接口设计，补充知识库占位目录、审计事件以及训练引用校验要求，准备进入开发阶段。
- 2025-10-31 16:10 UTC 完成后端 API、迁移与 pytest；前端反馈面板与训练向导引用上线，更新技术规范与 UX 文档。
- 2025-10-31 16:45 UTC 处理评审指出的仓储覆盖 bug，恢复 `EvaluationJobRepository.update` 并验证反馈状态更新接口。
- 2025-10-31 17:05 UTC 调整训练反馈摘要 API 支持空项目参数并仅返回 TODO 项，补充 pytest 验证。

### Completion Notes List

- 新增 `evaluation_feedback` 数据模型与 CRUD/导出 API，所有反馈操作写入审计日志并支持知识库 JSON/Markdown 占位。 
- `EvaluationReportPage` 集成反馈面板（评论、TODO、业务指标），支持筛选、标记完成、导出知识库并与训练向导联动。 
- 训练向导调用 `/training/feedback-summaries` 自动拉取待办反馈，提供“一键填充备注”功能形成评估→训练闭环。 
- 更新技术规格、UX 文档与 Story 情报，补充评估反馈模块调度与 UI 行为说明。
- 修复 `EvaluationFeedbackRepository.update` 被误覆盖导致反馈 PATCH 接口报错的问题。
- 优化训练反馈摘要过滤逻辑，支持未指定项目 ID 的查询并仅返回开放 TODO。
- 执行 `PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_evaluation_feedback.py -q` 验证反馈 CRUD、导出与摘要流程。

### File List

- backend/app/models/evaluation.py
- backend/app/models/__init__.py
- backend/app/repositories/evaluation.py
- backend/app/services/evaluation.py
- backend/app/services/training.py
- backend/app/api/evaluation.py
- backend/app/api/training.py
- backend/app/schemas/evaluation.py
- backend/app/schemas/training.py
- backend/migrations/versions/0016_evaluation_feedback.py
- backend/tests/test_evaluation_feedback.py
- frontend/src/lib/api.ts
- frontend/src/app/evaluation/EvaluationFeedbackPanel.tsx
- frontend/src/app/evaluation/EvaluationReportPage.tsx
- frontend/src/app/evaluation/EvaluationReportPage.test.tsx
- frontend/src/app/training/TrainingWizardPage.tsx
- frontend/src/app/training/TrainingWizardPage.test.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
- docs/sprint-status.yaml
- docs/stories/story-4.4.md
- backend/app/repositories/evaluation.py

## Senior Developer Review (AI)

- **结论**：通过。反馈 CRUD、导出与训练摘要联动均按验收标准运行，阻断问题已修复。
- **验证**：`PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_evaluation_feedback.py -q`
