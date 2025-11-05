<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- 产品简报强调“沉淀最佳实践到知识库，累计可复用模板”以支撑解决方案团队交付。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:90-110]
- 架构文档将 `KnowledgeBaseService` 列为治理协作模块的关键组件，需要与看板/通知并行提供知识沉淀能力。[来源: docs/architecture.md:63-79]
- Epic 6.4 要求支持上传文档/脚本/配置、打标签，并能将模板复制给新项目，同时具备版本控制与权限约束。[来源: docs/epics.md:360-368]
- 早期故事（3.5、4.4）已在训练/评估域输出导出能力，知识库需吸收这些 Artefact 并提供统一的检索与复用入口。[来源: docs/stories/story-3.5.md:40-63; docs/stories/story-4.4.md:32-52]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与已有资产
- 新增 SQLModel（`knowledge_entries`, `knowledge_entry_versions`）及 Alembic 迁移，沿用治理模块的 workspace/project 作用域与审计字段，对应 `backend/app/models/knowledge.py` 与 `backend/migrations/versions/0025_knowledge_base.py`。
- `KnowledgeBaseService` 复用 `PermissionService`、`WorkspaceRepository`、`AuditLogRepository`，提供条目 CRUD、版本管理、模板克隆等能力，存储结构落在 `storage_root/<workspace>/<project>/knowledge/library/entry-*` 下。[来源: backend/app/services/knowledge.py]
- API 通过 `/api/v1/knowledge` 路由暴露列表、详情、创建、版本追加与模板复制接口，Schema 扩展见 `backend/app/schemas/knowledge.py`，依赖注入在 `backend/app/api/deps.py`。
- 写入测试 `backend/tests/test_knowledge_base.py` 验证文档版本落盘、模板克隆及 JSON 配置保持一致，并回归 Story 6.2/6.3 的组合场景确保通知/治理调用兼容。
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 6.4: 知识库与模板沉淀

Status: Done
<!-- story_header:end -->

## Story

作为解决方案架构师，  
我希望把成功案例、脚本与模板沉淀到知识库，  
以便后续项目可以快速复用并持续演进。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 支持上传/保存文档、脚本、配置模板，能够打标签与描述。
2. 为模板类条目提供“一键复制到新项目”能力，并保留版本信息与审计记录。
3. 知识条目支持版本管理与权限控制（仅具备 `approval_manage` 的成员可写、克隆）。
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 数据层：新增 `knowledge_entries` / `knowledge_entry_versions` 模型与 Alembic 迁移，落地枚举 `KnowledgeEntryType` 并引入 `knowledge/library` 目录结构。[来源: backend/app/models/knowledge.py; backend/migrations/versions/0025_knowledge_base.py]
- [x] 服务层：实现 `KnowledgeBaseService`、仓储与审计记录，包含条目创建、版本追加、模板克隆与文件持久化逻辑。[来源: backend/app/services/knowledge.py; backend/app/repositories/knowledge.py]
- [x] API：在 `/api/v1/knowledge` 暴露列表/详情/新增/版本/克隆接口，补充 Pydantic Schema、依赖注入与主路由汇总。[来源: backend/app/api/knowledge.py; backend/app/schemas/knowledge.py; backend/app/api/deps.py; backend/app/api/router.py]
- [x] 测试：编写 pytest 用例验证文档版本落盘、模板克隆及 JSON 配置一致性，并回归治理协作相关用例。[来源: backend/tests/test_knowledge_base.py]
<!-- tasks_subtasks:end -->

## Validation

- `PYTHONPATH=/Users/zephyr/Desktop/workspace/jinfull/codex/llm-finetune-platform backend/venv/bin/pytest backend/tests/test_knowledge_base.py backend/tests/test_notifications.py backend/tests/test_governance_collaboration.py backend/tests/test_governance_kanban.py`

## Notes

- 知识条目默认写入 `storage_root/<workspace>/<project|general>/knowledge/library/entry-*/v{n}.{ext}`，文本类为 Markdown/TXT，模板类为 JSON，便于后续外部知识库或 BI 工具挂载。
- 模板克隆会复制标签、描述与配置快照，并生成新的条目，方便后续在目标项目继续迭代；若需自动生成训练向导草稿，可在后续迭代与 `TrainingWizardDraft` 对接。
- 当前权限策略：任意成员可读取，具备 `approval_manage` 的成员可创建/版本化/克隆；如需更细粒度控制，可在角色矩阵中增加知识库专属 operation。
