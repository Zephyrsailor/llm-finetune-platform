# Decision Architecture

## Executive Summary

llm-finetune-platform 采用 “React Web 控制台 + FastAPI 单体服务 + 训练执行任务队列” 的三层架构：前端基于 React 18 + Vite + Tailwind CSS + shadcn/ui 提供引导式体验，后端使用 FastAPI 聚合数据、训练、评估、部署逻辑，通过 Celery/Redis 调度 GPU 任务，vLLM 暴露推理服务。PostgreSQL 管理关系数据，初期使用本地文件系统保存语料、模型与评估 artefacts（预留 S3 迁移路径）。一期内的可观测方式采用标准 Python logging 搭配平台内置的“Training Log” 面板呈现实时日志；后续再视需要引入 Prometheus/Grafana 等完整方案。该设计兼顾 PRD 的安全、可靠、可扩展要求，同时维持 MVP 阶段的实现复杂度。

**关键工程决策提示（可按需微调）：**

- 前端：React 18 + Vite + Tailwind + shadcn/ui，保持轻量且易于自定义。  
- 后端：FastAPI 单体 + Celery 任务 + SQLModel + Alembic，统一在一个 `backend` 仓内维护。  
- 运行方式：Docker Compose 管理前后端、任务队列、Redis、Postgres、vLLM；初期 artifacts 落在本地文件系统，前端提供 Training Log 面板查看日志。

## Decision Summary

| Category | Decision | Version | Affects Epics | Rationale |
| -------- | -------- | ------- | ------------- | --------- |
| 前端框架 | React 18.2 + Vite 5 + Tailwind 3.4 + shadcn/ui | ✅ (starter) | 全部，尤指 E4/E6 | 组合轻量、可控，便于自定义 UI 与快速开发 |
| 状态管理 & 数据请求 | TanStack Query 5.39 + Zustand 4.5 | 2025-10-23 | E2-E6 | 支持请求缓存、实时刷新与离线容错 |
| 后端服务 | FastAPI 0.111.x + Pydantic 2.6.x 单体 | 2025-10-23 | E2-E6 | 高性能 async、自动 OpenAPI、与 ML 生态一致 |
| 任务调度 | Celery 5.4.x + Redis 7.2 | 2025-10-23 | E2/E3/E4/E5 | 异步训练/评估/部署，内建重试/ACK 机制 |
| 数据库 | PostgreSQL 15.6 | 2025-10-23 | 所有 | 关系型事务、JSONB 支持、成熟生态 |
| 对象存储 | 本地文件系统 + 约定目录（后续可切换 S3/OSS） | 2025-10-27 | E2/E3/E5 | MVP 直接复用宿主文件系统，降低部署难度，并预留云存储迁移路径 |
| 缓存/事件 | Redis 7.2（Pub/Sub + Streams） | 2025-10-23 | E2-E5 | 训练进度推送、缓存 Dashboard、速率限制 |
| 训练执行 | PyTorch 2.3 + HF Transformers 4.45 + PEFT 0.11（QLoRA/DoRA） | 2025-10-23 | E2/E3 | 满足参数高效微调需求，可扩展 TRL |
| 推理服务 | vLLM 0.4.2 | 2025-10-23 | E5 | 高吞吐、PagedAttention、支持多模型路由 |
| 观测平台 | Python logging + 平台内 Training Log 面板（Prometheus/Grafana 为后续升级） | 2025-10-27 | E3/E4/E5/E6 | 直接在前端展示实时日志，满足 MVP 透明度，可随时升级扩展 |
| 身份与权限 | 自建账号 + JWT + RBAC + MFA，留白 OIDC SSO | 2025-10-23 | E1/E6 | 满足权限矩阵与审计版本化 |
| 部署平台 | Docker Compose + NVIDIA Container Toolkit | 2025-10-27 | E5 | 单机部署即可运行全部组件，配置简单且便于调试 |

## Project Structure

```
llm-finetune-platform/
├── docs/                       # PRD、架构、Epic、UX 等文档
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，挂载 API 与后台任务
│   │   ├── api/                 # REST 路由（数据/训练/评估/部署/治理）
│   │   ├── core/                # 配置、依赖注入、安全
│   │   ├── services/            # 领域服务（DataHubService 等）
│   │   ├── repositories/        # 数据库访问层
│   │   ├── schemas/             # Pydantic/SQLModel 模型
│   │   └── tasks/               # Celery 任务（训练、评估、部署）
│   ├── migrations/              # Alembic 迁移脚本
│   ├── tests/                   # 后端与任务单元测试
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # 页面路由（Vite + React Router）
│   │   ├── components/          # 统一存放自定义组件与通过 shadcn/ui 生成的部件
│   │   ├── hooks/               # TanStack Query/Zustand hooks
│   │   ├── lib/                 # 工具函数、常量
│   │   └── styles/              # Tailwind 全局样式与 tokens
│   ├── public/
│   └── Dockerfile
├── docker/
│   ├── docker-compose.yml       # 一键启动前后端、Redis、Postgres、vLLM
│   └── env/                     # 环境变量样例（.env.example 等）
├── scripts/                     # 初始化、填充数据、开发辅助脚本
└── README.md
```

## Epic to Architecture Mapping

| Epic | 模块/服务 | 关键组件 | Notes |
|------|-----------|----------|-------|
| E1 平台基础与访问控制 | backend.app.api.auth、frontend.app/(auth) | AuthController、RBACService、WorkspaceRepository | 管理账号、工作空间、权限；后续扩展 SSO |
| E2 数据与语料工作台 | backend.app.api.data、services.data_hub、frontend DataHub pages | DatasetRepository、DataPipelineOrchestrator、QualityAnalyzer | 调度清洗/脱敏流水线，落地质量仪表盘 |
| E3 微调执行引擎 | backend.app.api.training、backend.app.tasks.training | TrainingConfigService、Celery Queue `training`, GPU Runner | 启动训练向导、异步执行微调、快照管理 |
| E4 评估与报告中心 | backend.app.api.evaluation、backend.app.tasks.evaluation、frontend Evaluation pages | EvaluationRunner、ReportBuilder、FeedbackService | 自动评估、生成报告、评论反馈 |
| E5 部署与运营监控 | backend.app.api.deployment、backend.app.tasks.deployment、vLLM controller | ModelRegistryService、DeploymentManager、MetricsCollector | 部署管理、灰度、QPS/延迟监控 |
| E6 治理协作与知识沉淀 | backend.app.api.governance、frontend Governance pages | KanbanService、NotificationHub、KnowledgeBaseService | 看板、审批、通知、知识库 |

## Technology Stack Details

### Core Technologies

- **Frontend**：React 18、TypeScript、Vite 5、Tailwind CSS、shadcn/ui、TanStack Query、Zustand、Recharts。  
- **Backend**：Python 3.11、FastAPI、Pydantic v2、SQLModel、SQLAlchemy、Celery、Redis、Alembic、OpenAPI。  
- **任务执行**：Celery Worker（并入 backend `tasks`）+ PyTorch + HuggingFace Transformers + PEFT（QLoRA/DoRA）、bitsandbytes、Accelerate。  
- **数据层**：PostgreSQL 15、Redis、（可选）FAISS/Milvus；静态 artefacts 暂存在本地文件系统目录，预留 S3/OSS 接入。  
- **Observability**：Python logging（JSON 格式可选）、后端 SSE/WebSocket 输出训练日志，前端 Training Log 面板实时展示；FastAPI /health 与 /metrics（轻量）端点；Prometheus/Grafana 作为后续增强。  
- **DevOps**：Docker / Docker Compose、GitLab CI 或 GitHub Actions、自托管 GPU 节点（NVIDIA Container Toolkit）。

### Integration Points

| 集成 | 描述 | 接口形式 |
|------|------|----------|
| GPU 节点 | 单机 GPU Server（RTX 4090/5090、A100 等），Docker 直接挂载 | Docker Runtime + NVIDIA Container Toolkit |
| vLLM 服务 | 独立容器，通过 docker-compose 管理生命周期 | REST/gRPC + 内部 token |
| 模型/数据 artefacts | 本地挂载目录（`/var/lib/llmft/artifacts`），预留迁移至 S3 | Python `pathlib`/`shutil`，后续可接入 boto3 |
| 通知渠道 | 企业微信/Slack/Webhook/Email | Backend NotificationHub + 外部 Webhook API |
| 基础监控 | 后端日志流 + Training Log 前端面板 | JSON/文本日志 + UI 展示 |

### Novel Pattern Designs

- **Async Event Hub Pattern**：使用 Redis Stream 将训练、评估、部署事件异步广播给仪表盘与通知中心，避免耦合。  
- **Data Version Snapshot Pattern**：每次清洗与转换生成不可变版本号，并通过 artefact 目录（`/var/lib/llmft/datasets`）+ PostgreSQL 元数据追踪，使回滚和审计变得简单。  
- **Evaluation Gate Pattern**：部署 API 强制检查最新评估结果状态，未通过则禁止上线，实现质量闸门。

### Model Registry & Deployment Gate
- `ModelRegistryService` 负责注册模型、创建版本并维护 artefact 目录结构；版本状态枚举 `candidate/production/deprecated` 通过 `model.version.status_changed` 事件通知部署流水线。  
- Promotion 流程会查询 `evaluation_jobs`，确保最近一次评估状态为 `COMPLETED`，且 `metrics_json.thresholds.*.triggered` 均为 false，否则抛出 `ModelVersionPromotionError` 并写入审计日志。  
- 导出接口将模型版本元数据写入 `/models/workspace-{id}/project-{id|general}/model-{id}/exports/`，供运营、治理模块纳入知识库。  
- 部署模块通过 `DeploymentService` 发起 Celery 任务（`deployment.run_deployment` → `deployment.health_check`），在 `deployments`/`deployment_instances`/`deployment_events` 中记录状态演进；健康检查通过后落盘 endpoint/token，失败则触发 `deployment.rollback` 回退。  
- 推理接入层 `InferenceService` 提供 REST/gRPC 调用入口，管理 API Key、限流配额与调用日志（`inference_api_keys`、`inference_usage`、`inference_calls`），并复用部署信息选择可用模型实例。

## Implementation Patterns

1. **Domain Service + Repository 模式**：每个领域（DataHubService、TrainingService 等）提供原子操作，Repository 负责数据库交互；AI 代理在实现故事时优先调用服务层。  
2. **Task Blueprint**：后台任务以 `tasks/<domain>/<action>_task.py` 组织，并在 README 中列出参数及幂等性要求，避免代理创建重复任务；首个故事需要完成 Celery/Vite 基础结构并提交可运行代码。  
3. **API Contract First**：所有 API 先在 `shared/contracts/openapi.yaml` 定义，再在前后端生成类型，确保一致性。  
4. **Event Hook Registry**：通知与审核通过 `notifications/hooks.yaml` 注册，代理新增事件必须先更新此注册表。  
5. **Runtime Guard**：Docker 相关配置集中在 `docker/` 目录（compose、环境变量示例、启动脚本），禁止在文档或零散脚本中硬编码端口/网络。

## Consistency Rules

### Naming Conventions

- Python 模块/文件 `snake_case`，类名 `PascalCase`，异步函数以 `_async` 结尾。  
- React 组件 `PascalCase`，hooks `useSomething`，API hooks `use<Domain><Action>`.  
- 数据库表名 `plural_snake_case`（如 `dataset_versions`），主键 `id`，外键 `*_id`.  
- Celery 队列命名：`<domain>.<action>`（例如 `training.execute`）。  
- 对象存储路径：`workspaces/{workspace_id}/datasets/{dataset_id}/v{version}/`.

### Code Organization

- backend.app 按 `api/`, `services/`, `repositories/`, `schemas/`, `core/`, `tasks/` 划分。  
- 前端在 `src/app` 使用 React Router 管理页面，`src/components` 同时存放自定义组件与通过 shadcn/ui 生成的组件。  
- 共享 types（OpenAPI、前后端共享模型）放在 `backend/app/contracts` 与 `frontend/src/lib/types`，通过脚本生成。
- 所有配置统一使用 `.env` + Pydantic Settings，环境变量前缀 `LLMFT_`.

### Error Handling

- FastAPI 使用 `HTTPException` 与自定义 `AppError`，集中在 `core/exceptions.py`。  
- Celery 任务捕获异常并记录上下文日志，同时写入 `task_failures` 表。  
- 前端采用 toast + inline 错误组合，关键操作（训练/部署）提供重试按钮。  
- 定义统一错误码：`DATA_*`, `TRAIN_*`, `DEPLOY_*`，便于排查。

### Logging Strategy

- Backend 与任务模块使用 Python `logging`（可选 JSON Formatter）输出请求 ID、工作空间 ID、任务 ID 等关键字段，同步写到标准输出与滚动文件。  
- 前端提供 `Training Log` 面板，通过 WebSocket/SSE 订阅后台日志流，实时渲染训练/评估进度；同时保留浏览器 console 日志与可选 Sentry。  
- 重要操作写入 PostgreSQL `audit_logs`，保留 1 年并定期归档至 artefact 目录。  
- 运维人员可通过 CLI `tail` 或下载日志文件排查问题；Prometheus Exporter 等高级监控放入 Phase 4 待办。

## Data Architecture

主要实体与关系（括号为关键字段）：

- `workspace (id, name, plan)` ↔ `project (id, workspace_id, name, status)`。  

- `workspace_member (workspace_id, user_id, role)` 维护可访问成员，与 Story 1.1 权限体系协同。  
- `role (id, workspace_id, key, name, is_system)` ↔ `role_permission (role_id, operation)` ↔ `workspace_member_role (workspace_id, user_id, role_id)` 存储角色矩阵与操作权限映射。默认内置管理员、数据、训练、运维、业务审阅 5 类角色，并以 `data_import`、`training_launch`、`deployment_manage`、`evaluation_view`、`approval_manage` 操作枚举表达权限范围，可按工作空间扩展。  
- 默认 artefact 路径：`storage/workspaces/{workspace_id}/projects/{project_id}/`，其中会初始化 `docs/`, `datasets/`, `pipelines/` 目录及 `docs/README.md` 占位文档。

- `dataset (id, project_id, source, type)` ↔ `dataset_version (id, dataset_id, version, quality_scores, location_uri)`。  
- `training_job (id, project_id, status, template, created_by)` ↔ `training_run (id, job_id, dataset_version_id, metrics_json, snapshot_uri)`。  
- `evaluation_run (id, training_run_id, testset_version_id, metrics_json, report_uri)`。  
- `model_version (id, project_id, training_run_id, status)` ↔ `deployment_instance (id, model_version_id, environment, endpoint_url, qps, latency_stats)`。  
- `notification (id, project_id, event_type, payload_json)`、`kanban_task`, `approval_request` 支撑治理模块。  
- 所有实体包含 `created_at`, `updated_at`, `created_by` 字段以支持审计。

## API Contracts

- `POST /api/v1/datasets`：上传/注册数据集，返回 dataset_id；支持对象存储预签名地址。  
- `POST /api/v1/datasets/{id}/versions`：触发清洗/脱敏/转换并生成版本。  
- `POST /api/v1/training-jobs` → `TrainingService.schedule_job`；`GET /api/v1/training-runs/{id}` 查询状态与指标。  
- `POST /api/v1/evaluations`：针对训练 run 发起评估；`GET /api/v1/evaluations/{id}/report` 返回图表数据与导出链接。  
- `POST /api/v1/model-versions/{id}/deploy`：通过质量闸门后方可执行；`POST /api/v1/model-versions/{id}/rollback`.  
- `GET /api/v1/dashboard/summary`：聚合展示 Dashboard 卡片数据。  
- `POST /api/v1/governance/approvals`：创建审批请求；`PATCH /api/v1/governance/approvals/{id}` 更新结果。  
- `POST /api/v1/workspaces` / `PATCH /api/v1/workspaces/{id}`：管理工作空间生命周期；`POST /api/v1/workspaces/{id}/projects` 初始化项目并生成默认目录；`GET /api/v1/workspaces` 返回成员可访问的工作空间清单。  
- `GET /api/v1/workspaces/{id}/roles`：查询工作空间角色矩阵（角色列表、成员分配、权限枚举）；`POST /api/v1/workspaces/{id}/roles` / `PATCH /api/v1/workspaces/{id}/roles/{roleId}`：创建与更新角色定义；`POST /api/v1/workspaces/{id}/members/{memberId}/roles`：绑定成员角色。  
- API 采用 JWT 鉴权（Header `Authorization: Bearer <token>`），支持分页、过滤、审计日志 header（`X-Request-ID`）。

## Security Architecture

- 身份认证：平台账号 + 密码 + MFA；后端使用 JWT + Refresh Token；密码/密钥由 Argon2 哈希存储。  
- 权限：RBAC（角色→权限项），结合对象级 ACL（工作空间成员）。平台以工作空间为作用域预置 5 种系统角色（管理员、数据、训练、运维、业务审阅），分别绑定 `data_import`、`training_launch`、`deployment_manage`、`evaluation_view`、`approval_manage` 操作。成员可绑定多个角色，后续可在此基础上引入 ABAC 扩展。工作空间操作的权限校验通过 PermissionService 汇聚角色权限；若拒绝访问，会写入 `audit_logs`（事件 `authz.workspace.denied`，记录 workspace_id、operation、reason 等）。角色管理 API 由 RoleManagementService 统一执行业务校验并产生日志：`workspace.role.created`、`workspace.role.updated`、`workspace.role.assignment`。  
- 数据安全：上传数据写入本地 artefact 目录，使用文件系统权限 + AES 加密工具（可选）保护敏感内容；迁移 S3 时再启用 SSE-KMS。  
- 审计：所有 CRUD 操作写入 `audit_logs`，保留操作人、请求源、变更 diff。  
- 网络：前端、后端、任务队列、vLLM 通过 docker-compose 内部网络通信；需要外露 API 时可加 Nginx 反向代理 + HTTPS。
- 合规：预留 GDPR/金融合规字段（数据保留策略、用户删除请求处理）。

## Performance Considerations

- 异步任务 + 分布式 worker 承载训练/评估高耗时操作。  
- 可将常用概览指标缓存于 Redis（TTL 60s）。  
- vLLM 节点使用 PagedAttention + Tensor 并发提升吞吐。  
- 针对大规模数据上传，支持分段/断点续传与后端批处理。  
- 数据库索引：workspace_id + status、project_id + created_at 等常用查询字段。  
- 前端使用懒加载、Suspense、Streaming 数据表格提高渲染性能。

## Deployment Architecture

- 使用 `docker/docker-compose.yml` 编排所有核心服务：frontend、backend、celery-worker、redis、postgres、vllm、flower。  
- GPU 主机需安装 NVIDIA 驱动与 Container Toolkit，compose 通过 `deploy.resources` 或 `--gpus all` 把显卡映射给 Celery/vLLM 容器。  
- 环境变量集中在 `docker/env/.env.*` 文件，执行 `docker compose --env-file docker/env/.env.dev up` 即可启动。  
- CI/CD 只需构建前后端镜像并推送 registry，目标环境拉取后运行同一套 compose 文件。  
- 预留 `docker/compose.prod.yml`，加入 nginx 反向代理、卷持久化与集中日志收集；当部署规模扩大时可评估迁移至 Kubernetes。

## Development Environment

### Prerequisites

- Python 3.11+、Node.js 20+、pnpm 8、Docker 24+、Docker Compose。  
- GPU 开发需安装 NVIDIA 驱动 + CUDA 12.2 + cuDNN；本地启动 compose 时可使用 `--gpus all`。  
- 后端依赖通过 `uv`（或 Poetry）管理，前端依赖使用 pnpm。

### Setup Commands

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Celery worker (同仓启动)
uv run celery -A app.tasks.worker worker -Q training,evaluation,deployment --loglevel=info

# Frontend
cd frontend
pnpm install
pnpm dev

# Local stack (Postgres/Redis/vLLM)
cd docker
docker compose up -d
```

## Architecture Decision Records (ADRs)

1. **ADR-001**：采用 FastAPI 单体服务 + Celery worker 架构，原因是首期团队规模小、需要快速迭代；未来可拆分为独立微服务。  
2. **ADR-002**：训练与推理统一使用自有 GPU 集群，避免云租赁成本波动；通过 Docker Compose + NVIDIA Container Toolkit 暴露显卡。  
3. **ADR-003**：数据处理选用 Pandas/Polars 而非 Spark，因首期数据规模可控且需快速迭代；后续若数据量极大再引入分布式框架。  
4. **ADR-004**：评估闸门强制化——部署前必须引用最新 Evaluation Run，并确保指标未退化超过阈值。  
5. **ADR-005**：统一日志采用 Python logging 输出到 stdout/文件，并通过平台内 Training Log 面板和 CLI tail 排查；关键操作写入 audit_logs，满足合规与溯源。

---

_Generated by BMAD Decision Architecture Workflow v1.0_  
_Date: 2025-10-23_  
_For: zephyr_
