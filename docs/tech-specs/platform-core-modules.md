# 平台核心模块技术规格

> 版本：2025-10-27  
> 适用范围：Solutioning Gate / Phase 4 实施前参考  
> 说明：文档定义核心后端模块的职责、接口、数据模型与异常处理策略，供 `create-story` 工作流和实施阶段直接引用。

---

## 1. AuthService（Story 1.1 底座）
- **职责**：账号注册、登录、会话刷新、登出、密码重置；记录安全审计日志。  
- **主要接口**  
  - `POST /api/v1/auth/register` → 创建用户、发送验证邮件。  
  - `POST /api/v1/auth/login` → 返回 Access/Refresh Token。  
  - `POST /api/v1/auth/logout` → 注销并失效 Refresh Token。  
  - `POST /api/v1/auth/refresh` → 刷新会话。  
  - `POST /api/v1/auth/password-reset/request` / `POST /api/v1/auth/password-reset/confirm`.  
- **数据模型**  
  - `users(id, email, password_hash, status, last_login_at, created_at, updated_at)`。  
  - `audit_logs(id, user_id, event_type, ip_address, user_agent, payload_json, created_at)`。  
  - `refresh_tokens(id, user_id, token_hash, expires_at, revoked)`。  
- **安全与异常**  
  - 密码使用 Argon2；刷新流程校验 Token 是否吊销。  
  - 登录失败 5 次内指数退避，超过阈值写入 `security_events`。  
  - 所有接口捕获 `ValidationError`、`AuthError`，统一返回 JSON `{code, message}`。

---

## 2. DataHubService
- **职责**：管理数据集、版本、清洗作业及质量指标。  
- **主要接口**  
  - `POST /api/v1/datasets` → 创建数据集（支持上传或外部 URI）。  
  - `POST /api/v1/datasets/{id}/versions` → 触发清洗/脱敏/转换；返回版本与清洗任务摘要。  
  - `GET /api/v1/datasets?workspace_id=...` → 按工作空间列出数据集；`GET /api/v1/datasets/{id}/versions` 查看历史版本。  
  - `GET /api/v1/datasets/{id}/versions/{version_id}` → 查看指标与状态。  
  - `POST /api/v1/datasets/{dataset_id}/cleaning/assignment` / `GET .../summary` → 维护清洗模板绑定与统计。  
  - `POST /api/v1/datasets/{dataset_id}/versions/{version_id}/quality/run` → 触发质量评估；`GET .../quality/summary` 查看指标；`GET .../quality/export` 下载报告。  
- **数据模型**  
  - `datasets(id, workspace_id, name, description, source_type, source_uri, storage_path, data_type, mime_type, file_size_bytes, checksum_sha256, tags[], notes, status, reference_dataset_id, created_by, created_at, updated_at)`。  
  - `dataset_versions(id, dataset_id, version, status, location_uri, stats_json, quality_summary_path, quality_report_manifest, created_by, created_at, updated_at)`。  
  - `data_cleaning_jobs(id, dataset_version_id, status, template_id, template_snapshot, logs_path, summary_path, export_manifest, error_message, created_at, updated_at, started_at, finished_at)`。  
  - `quality_evaluation_jobs(id, dataset_version_id, status, logs_path, summary_path, export_manifest, error_message, created_at, updated_at, started_at, finished_at)`。  
- **Artefact 目录结构**  
  - `/var/lib/llmft/datasets/{workspace}/{dataset_id}/v{n}/raw|logs|clean`，日志在 `logs/job-{id}.log` 中持续写入。  
  - 质量评估报告落地 `/var/lib/llmft/datasets/{workspace}/{dataset_id}/v{n}/quality/summary.json`、`anomalies.csv`，导出接口直接返回该路径。  
- **任务调度**  
  - 通过 Celery 任务 `data_cleaning.run_initial_cleaning` 将版本置为 `processing → completed` 并落地日志；清洗完成后自动调度 `data_cleaning.run_quality_evaluation`，生成质量指标与报告。  
- **异常处理**  
  - 清洗作业失败 → 更新 `status=failed`，写入 `data_cleaning_jobs.logs_path`，触发通知。  
  - 质量评估无法读取清洗结果时返回失败并在 logs 中给出原因；导出接口需校验 RBAC 并记录 `dataset.quality.export` 审计日志。  
  - 重复上传 → 若内容哈希一致，直接复用已有版本并记录引用。  
  - 超限校验 → 依据 `settings.max_dataset_size_bytes` 拒绝写入，返回 HTTP 413；所有创建/失败事件写入 `audit_logs`。  

---

## 3. TrainingService
- **职责**：协调训练任务生命周期，调度 Celery Worker，追踪训练运行。  
- **主要接口**  
  - `POST /api/v1/training-jobs` → 创建训练任务，校验数据版本、模型、资源配置。  
  - `GET /api/v1/training-jobs/{id}` → 返回任务状态、当前指标、日志链接。  
  - `POST /api/v1/training-jobs/{id}/cancel` → 请求终止任务。  
  - `GET /api/v1/training-runs/{run_id}/logs` → 以 SSE 或分页轮询方式返回日志流。  
  - `GET /api/v1/training/monitor/runs` → 返回训练运行的最新指标与告警概览。  
  - `POST /api/v1/training/monitor/alert-rules` / `PATCH /api/v1/training/monitor/alert-rules/{id}` → 创建/更新阈值规则。  
  - `POST /api/v1/training/monitor/alerts/{id}/status` → 更新告警处理状态；`GET /api/v1/training/monitor/metrics/export` / `alerts/export` → 导出指标与告警。  
  - `GET /api/v1/training/snapshots?workspace_id=&run_id=` → 列举快照；`GET /api/v1/training/snapshots/{id}` → 查看详情。  
  - `POST /api/v1/training/snapshots/{id}:resume` → 从快照断点续训；`POST /api/v1/training/snapshots/{id}:rollback` → 将模型 artefact 回滚至快照。  
  - `GET /api/v1/training/experiments?workspace_id=&job_id=` → 查询训练运行的元数据摘要；`GET /api/v1/training/experiments/{run_id}` → 返回完整元数据。  
  - `POST /api/v1/training/experiments/compare` → 对比两次运行的配置、指标、关联快照/告警；`POST /api/v1/training/experiments/export` → 按 JSON/CSV/Markdown 导出实验报告并写入审计日志。  
- **数据模型**  
  - `training_jobs(id, project_id, dataset_version_id, base_model, adapter_type, requested_gpus, queue_name, status, params_json, scheduled_by, scheduled_at)`。  
  - `training_runs(id, job_id, started_at, finished_at, metrics_json, artifact_uri, exit_code, resumed_from_snapshot_id, metadata_json)`。  
  - `training_events(id, run_id, timestamp, level, message)`（用于日志保留与 SSE 推送）。  
  - `training_metric_samples(id, run_id, metric, value, recorded_at)`（秒级指标采样，用于实时监控）。  
  - `training_alert_rules(id, workspace_id, name, metric, operator, threshold, cooldown_seconds, is_active, channels_json, created_by, created_at)`。  
  - `training_alerts(id, rule_id, run_id, value, status, triggered_at, acknowledged_at, resolved_at, notes)`。  
  - `training_snapshots(id, workspace_id, job_id, run_id, path, step, epoch, metrics_json, trigger_type, created_by, created_at, notes, restored_at, restored_by)`。  
- **GPU 策略**  
  - Worker 启动时记录 `torch.cuda.device_count()` 和 `nvidia-smi` 输出到 `runtime_gpu_inventory`。  
  - 默认单卡串行；如 `job.requested_gpus > 1`，通过 Redis 锁控制同一时间只有一个多卡任务。  
  - 失败处理：Celery `retry` 最多 1 次，仍失败则标记 `status=failed`，触发通知并释放 GPU 锁。  
- **资源配置校验**：训练向导提交时需提供 `requested_gpus` 与 `queue_name`，服务端根据 `settings.max_training_gpus` 与 `settings.training_gpu_queues` 校验范围，记录在 `training_jobs` 表并写入审计日志。  
- **异常处理**  
  - 参数校验失败 → HTTP 422，写入审计。  
  - Worker 超时/宕机 → Celery `soft_time_limit` + cleanup 脚本终止残留进程。  
  - 训练过程中写入 `training_events`；日志 API 读取同表并输出为 JSON `{timestamp, level, message}`。  
- **快照与回滚流程**  
  - 运行结束或达到阈值步骤时调用 `TrainingSnapshotService.create_snapshot`：将 checkpoint、优化器状态落地到 `storage/workspaces/{workspace}/training/{job}/runs/{run}/snapshots/{timestamp}`，同步写入 `training_snapshots` 表并记录审计。  
  - 监控告警或人工选择快照后调用 `/snapshots/{id}:resume`：新建 `training_runs(status=pending,resumed_from_snapshot_id=id)`，触发 Celery 任务 `training.run_job_from_snapshot` 在原 artefact 基础继续训练，并自动生成新的快照记录。  
  - `/snapshots/{id}:rollback` 将快照 artefact 拷贝到 `training/{job}/active/` 目录，写入 `evaluation.json` 占位报告并更新 `training_snapshots.restored_at/restored_by`，同时将相关告警标记为 `resolved`。  
  - 所有续训/回滚操作均要求具备 `training_launch` / `deployment_manage` 权限并写入 `training.snapshot.resume`、`training.snapshot.rollback` 审计事件，便于合规追溯。  
- **元数据聚合与实验管理**  
  - `TrainingExperimentService` 在 Celery 任务完成后自动构建 `metadata_json`：统一记录模型/数据版本、模板、超参、耗时/成本估算、最终指标、关联快照与告警列表。  
  - 前端实验页调用 `/experiments` 系列接口展示列表与详情；比较接口对参数、指标、资源维度生成 diff，并返回快照/告警引用，方便定位差异。  
  - 导出接口将运行元数据与对比结果持久化到 `storage/training/{workspace}/experiments/exports/`，返回相对路径供知识库或 BI 接入，同时写入 `training.experiment.exported` 审计事件。  
- **评估套件与任务（Story 4.1 新增）**  
  - `EvaluationService` 统一管理评估模板与任务，校验工作空间、项目、训练运行、数据版本关系，并写入 `evaluation_jobs`；内置模板在首次访问时通过 `_ensure_builtin_templates` 同步至 `evaluation_templates`。  
  - 主要接口：`GET /api/v1/evaluations/templates`、`GET /api/v1/evaluations/templates/{id}` 获取模板；`POST /api/v1/evaluations/jobs` 创建评估任务（支持上传文件或引用数据版本，并可绑定训练运行）；`GET /api/v1/evaluations/jobs` / `{id}` 查看任务状态与指标；`GET /api/v1/evaluations/jobs/{id}/export?format=markdown|json` 下载报告或指标。  
  - 数据模型：`evaluation_templates(id, key, name, task_type, metrics, config_json, is_builtin, workspace_id, created_at, updated_at)`；`evaluation_jobs(id, workspace_id, project_id, training_run_id, evaluation_template_id, dataset_version_id, dataset_path, artifact_path, report_path, status, metrics_json, error_message, created_by, created_at, updated_at, started_at, finished_at)`。  
  - Artefact 策略：评估输入与输出存放在 `/var/lib/llmft/{workspace}/{project|general}/evaluations/{job_id}/`，目录下包含 `input/`、`results.json`、`report.md`；Celery 任务 `evaluation.run_job` 在 eager 模式下生成占位指标与报告，后续可替换为真实计算逻辑。  
  - 权限与审计：创建、查看、导出接口均需 `evaluation_view` 操作；服务层通过 `PermissionService.require_operation` 校验，并写入 `evaluation.job.created`、`evaluation.job.completed`（失败时记录 `error_message`）。  
- **自动化评估流水线（Story 4.2 新增）**  
  - 训练任务完成后由 `run_training_job` 调用 `EvaluationService.schedule_automatic_evaluation`，基于工作空间默认模板与数据版本创建评估任务；幂等校验通过 `training_run_id + template_id` 去重，并新增 `trigger_mode` 字段区分自动/手动。  
  - `evaluation.run_job` 集成 `sacrebleu`、`rouge-score`、`evaluate` 等库计算 BLEU、ROUGE-L、Exact Match、Perplexity，同时生成 `baseline`、`delta`、`thresholds` 元数据存入 `metrics_json` 与 Markdown 报告。  
  - 指标低于阈值或评估失败时调用 `TrainingMonitoringService.record_evaluation_alert` 将事件写入训练告警体系（metric 名称 `evaluation_bleu`、`evaluation_perplexity` 等），并记录 `evaluation.metric.threshold_triggered` / `evaluation.alert.triggered` 审计。  
  - 训练运行 `metadata_json.evaluation` 维护最新任务 ID、指标与近 10 条历史记录；首次评估的指标保存为 `baseline_metrics` 供后续对比与 UI 展示。  
- **报告生成与可视化（Story 4.3 新增）**  
  - `EvaluationService.get_report_payload` 聚合评估指标、案例、训练上下文与数据集元信息，前端据此渲染指标卡片、案例表格与 Markdown 摘要（同时提供 HTML 版本供预览）。  
  - Celery 任务在 artefact 目录写入 `report.md`、`results.json`、`cases.json`，服务层追加 share token（JWT，默认 7 天有效期）与 PDF 导出（轻量 PDF 生成流程），并通过 `evaluation.report.share_created`、`evaluation.report.share_accessed`、`evaluation.report.exported` 审计事件留痕。  
  - 导出接口新增 `format=pdf`，默认返回 Markdown，同时复用 `/api/v1/evaluations/reports/{id}` 提供受控分享链接；训练监控页与报告页互相跳转并展示项目信息、基础模型、数据版本等引用关系。  
- **反馈与复盘记录（Story 4.4 新增）**  
  - 新增 `EvaluationFeedback` 模型与 `EvaluationFeedbackRepository`，覆盖评论、TODO、业务指标三类反馈；接口层提供创建、更新、删除、筛选与知识库导出（JSON/Markdown），写入 `evaluation.feedback.*` 审计事件。  
  - 反馈导出统一落地 `storage/{workspace}/{project|general}/knowledge/feedback/`，文件命名 `feedback-job-{id}-{timestamp}.md|json`，满足后续 KnowledgeBaseService/治理模块的数据接入。  
  - 训练服务可通过 `list_feedback_summaries` 查询待办反馈，在训练向导中引导用户将复盘 TODO 引入备注，形成“评估 → 训练”闭环。  

---

## 4. DeploymentManager
- **职责**：编排模型版本的 vLLM 部署、灰度放量与回滚，统一记录部署事件、健康状态与访问凭证。  
- **主要接口**  
  - `GET /api/v1/deployments` / `GET /api/v1/deployments/{id}` → 按工作空间/项目/状态查看部署与事件时间线。  
  - `POST /api/v1/deployments` → 选择模型版本、环境与资源参数后发起部署，触发 Celery 任务。  
  - `POST /api/v1/deployments/{id}/traffic` → 调整灰度流量占比（0~100%），记录 `deployment.traffic_adjusted` 事件。  
  - `POST /api/v1/deployments/{id}/rollback` → 手动回滚到上一稳定版本，写入审计日志与 `deployment.rolled_back` 事件。  
- **数据模型**  
  - `deployments(id, workspace_id, project_id, model_version_id, environment, status, endpoint_url, access_token, config_json, metrics_json, traffic_percent, notes, created_by, updated_by, created_at, updated_at)`。  
  - `deployment_instances(id, deployment_id, environment, status, endpoint_url, access_token, config_json, metrics_json, traffic_percent, health_checked_at, created_at, updated_at)`，记录实际运行实例的健康检查与流量配置。  
  - `deployment_events(id, deployment_id, event_type, level, message, payload_json, created_at)`，存放部署请求、健康检查、流量调整、回滚等节点。  
- **部署流程**  
  1. `DeploymentService.create_deployment` 校验工作空间/项目权限（`DEPLOYMENT_MANAGE`）、模型版本归属与生产状态，并执行评估闸门（检查 `metrics_json.thresholds.*.triggered`）。  
  2. 生成部署记录（初始 `pending`），写入 `model.version.deploy_requested` 审计事件，将任务提交到 Celery 队列 `deployment.run_deployment`。  
  3. `run_deployment_job` 标记状态为 `deploying` 并创建事件；紧接着调用 `run_deployment_health_check` 模拟 Compose/vLLM 启动与健康探针，生成 endpoint/token/初始指标。  
  4. 健康检查通过后调用 `DeploymentService.finalize_success`，将状态更新为 `active`，记录 `deployment.completed` 事件并保存指标、访问凭证。  
- **异常处理**  
  - 评估闸门未通过或模型版本不在生产状态 → 抛出 `ModelVersionPromotionError`，阻断部署并提示用户。  
  - 健康检查失败或 Celery 任务异常 → `finalize_failure` 将状态置为 `failed`，后续由 `run_deployment_rollback` 或手动回滚恢复，并记录 `deployment.failed`/`deployment.rolled_back` 事件与通知。  
  - 灰度流量参数非法会被服务层拒绝（0~100% 约束），保持部署状态与事件日志一致。

## 5. InferenceGateway
- **职责**：对外暴露推理 API/SDK 接入层，统一鉴权、限流、配额与调用日志，衔接 DeploymentManager 提供的活跃模型实例。  
- **主要接口**  
  - REST `POST /api/v1/inference` → 同步推理请求，支持批量输入与参数（temperature、max_tokens 等占位）。  
  - REST `GET /api/v1/inference/logs` → 分页查询调用日志，返回延迟、token 消耗、状态码，用于审计与计费。  
  - REST `GET /api/v1/inference/calls/{id}` → 查看单次调用详情（含错误信息、token 统计）。  
  - REST `POST /api/v1/inference/api-keys` / `GET` / `DELETE` → 管理推理 API Key（创建、查看、吊销），并返回一次性明文密钥。  
  - gRPC `llmft.inference.Inference.Invoke`（依赖 `grpcio` + `protobuf`）→ 与 REST 对齐的推理接口，便于偏后端语言集成。  
- **数据模型**  
  - `inference_api_keys(id, workspace_id, name, key_prefix, key_hash, rate_limit_per_minute, daily_quota, is_active, created_by, revoked_at, last_used_at, created_at, updated_at)`。  
  - `inference_usage(id, workspace_id, scope[minute|day], window_start, request_count, token_count, created_at, updated_at)` 聚合限流/配额窗口。  
  - `inference_calls(id, workspace_id, project_id, deployment_id, model_version_id, api_key_id, user_id, request_payload, response_payload, status, latency_ms, input_tokens, output_tokens, error_message, created_at)`。  
- **限流与配额**  
  1. 服务层 `_enforce_limits` 依据 `settings.inference_rate_limit_per_minute` 与 `settings.inference_daily_quota`，叠加 API Key 自定义阈值（若有），在事务中更新 `inference_usage`。  
  2. 超限时抛出 `RateLimitExceeded`，API 返回 429 并记录 `inference_calls.status=rate_limited`、审计事件 `inference.rate_limited`。  
- **鉴权策略**  
  - 用户调用：复用 JWT + RBAC（新增 `RoleOperation.INFERENCE_USE`），默认分配给 `workspace-admin`、`operations-engineer`、`application-developer` 角色。  
  - API Key 调用：请求头 `X-LLMFT-API-Key`，通过 `key_prefix` + Argon2 哈希校验，支持吊销与最后使用时间追踪，并记录 `inference.api_key.created` / `revoked` 审计事件。  
- **日志与监控**  
  - 每次调用写入 `inference_calls`，记录输入/输出 token、延迟、错误信息，可按工作空间过滤；前端 `InferenceConsolePage` 提供调用统计、API Key 管理与调试入口。  
  - 监控模块（Story 5.4）直接读取 `inference_usage` 与 `inference_calls`，展示 QPS、配额使用情况并对接告警。  
- **客户端 SDK**  
  - Python 包 `sdk/python/llmft_client` 与 JS 包 `sdk/js/llmft-client` 封装鉴权与请求流程，示例与 Quickstart 位于各自 README；可扩展重试、流式响应等能力。  
- **依赖与配置**  
  - 核心依赖：`grpcio`, `protobuf`, `httpx`（Python SDK），`fetch`（JS SDK）。  
  - 默认限流参数由 `settings.inference_rate_limit_per_minute`、`settings.inference_daily_quota` 控制，可在 API Key 级别覆盖。

---

## 6. ModelRegistryService（Epic 5.1）
- **职责**：管理模型注册、版本关联、评估闸门与导出流程，形成部署与审批的单一事实源。  
- **主要接口**  
  - `GET /api/v1/models` → 根据工作空间/项目/状态过滤模型与版本；`GET /api/v1/models/{id}` → 获取模型详情。  
  - `POST /api/v1/models` → 注册模型，写入基本信息与标签，绑定工作空间与项目。  
  - `POST /api/v1/models/{id}/versions` → 创建版本，记录训练运行、评估任务、artefact 路径与备注。  
  - `PATCH /api/v1/models/{id}/versions/{version_id}` → 版本状态切换，执行 Evaluation Gate 检查并生成审计事件。  
  - `POST /api/v1/models/{id}/versions/{version_id}:export` → 导出版本元数据（JSON/Markdown）至知识库占位路径。  
- **数据模型**  
  - `registered_models(id, workspace_id, project_id, name, description, base_model, tags[], created_by, updated_by, created_at, updated_at)`。  
  - `model_versions(id, model_id, version, status, artifact_path, metadata_json, training_run_id, evaluation_job_id, evaluation_metrics_json, evaluation_report_path, deployment_target, notes, created_by, updated_by, promoted_by, promoted_at, created_at, updated_at)`。  
  - `model_version_status` ENUM（candidate/production/deprecated），Promotion 时校验评估阈值是否触发。  
- **Artefact 策略**  
  - 目录：`/var/lib/llmft/models/workspace-{id}/project-{id|general}/model-{id}/v{n}`；导出结果写入 `.../exports/{timestamp}.json|md`。  
  - 事件：版本状态变更写入 `model.version.status_changed`，供部署与通知模块订阅。  
- **异常处理**  
  - 无评估或评估未通过 → 抛出 `ModelVersionPromotionError` 并阻断生产发布。  
  - 模型名重复或跨工作空间访问 → 返回 400/403，写入 `audit_logs`。

## 7. Training Log 接口（平台日志面板）
- **职责**：向前端 Training Log 面板提供实时日志流。  
- **接口规范**  
  - SSE：`GET /api/v1/training-runs/{run_id}/stream`，返回 `text/event-stream`，消息格式：  
    ```
    event: log
    data: {"timestamp":"2025-10-27T10:21:00Z","level":"INFO","message":"loss=1.23, lr=5e-4"}
    ```  
  - 分页回放：`GET /api/v1/training-runs/{run_id}/logs?after=<iso8601>&limit=200`。  
- **数据来源**：`training_events` 表或对应的日志文件（默认写入数据库，超过阈值时滚动至文件）。  
- **安全与脱敏**  
  - 日志写入前过滤 Access Token、密钥、PII；关键字段采用星号替换。  
  - 仅允许关联项目成员访问；请求需带有效 JWT。  
- **存储策略**  
  - 实时日志保留 30 天；超过后归档至 `/var/lib/llmft/logs/archive/{run_id}.log.gz`。  
  - 提供 `log_retention_days` 配置，Cron 作业每日清理过期日志。

---

## 8. GPU 与 Artefact 运维策略
- **GPU 使用**  
  - Compose 启动命令统一加 `--gpus all`；Celery worker 读取 `CUDA_VISIBLE_DEVICES` 控制可用 GPU。  
  - 训练队列默认串行执行；当 `allow_parallel_gpu=true` 时，通过 Redis 分布式锁 `<gpu_id>` 控制同卡只跑一个任务。  
  - 任务结束后执行清理脚本：释放锁、调用 `nvidia-smi --gpu-reset`（可选）并归档日志、模型快照。
- **Artefact 管理**  
  - 目录：`/var/lib/llmft/{workspace}/{project}/{type}/...`，type 包含 `datasets`, `training`, `models`, `evaluations`, `logs`。  
  - 容量阈值：默认 80% 触发告警，90% 禁止新任务并通知运维。  
  - 清理策略：  
    1. 每周 Cron 根据 `retention_policy` 删除过期训练日志与临时文件。  
    2. 模型版本保留最近 N=5 个，可手动锁定防删除。  
  - 备份：重要 artefact（模型、评估报告）通过脚本同步至对象存储或冷备目录；协作方已确认 MVP 阶段接受本地磁盘存储方案，依据本策略执行。

---

## 9. 即时 Story 生成指引（摘要）
- `create-story` 工作流输入：  
  - PRD 功能/非功能段落链接；  
  - Architecture/tech-spec 节点；  
  - UX 章节或设计稿引用；  
  - 相关风险/依赖。  
- 输出：`docs/stories/story-<epic>.<index>.md`，结构与 `story-1.1` 相同（背景、验收标准、实现建议、依赖、风险）。  
- 生成后操作：  
  - 在 `docs/bmm-workflow-status.md` 的 `ORDERED_STORY_LIST` 添加条目，更新 TODO/IN_PROGRESS 字段；  
  - 若故事需要评审，在 PR/Issue 中附带引用。  
- 建议先演练 `create-story` 生成 Story 1.2，确认流程通畅后再进入 Phase 4。

---

如需扩展，请在对应模块下追加子章节并更新 Architecture/technical-decisions 中的引用。

---

## 9. WorkspaceService（Story 1.2 新增）
- **职责**：管理工作空间及其项目生命周期，控制成员权限，触发默认目录/占位文档生成，并对关键操作写入审计日志；同时初始化并维护工作空间级角色矩阵。
- **主要接口**  
  - `POST /api/v1/workspaces` → 创建工作空间，自动将当前用户标记为 owner，可附带成员列表。  
  - `PATCH /api/v1/workspaces/{id}` → 更新名称/描述/计划或切换 `active ↔ archived` 状态。  
  - `GET /api/v1/workspaces` / `{id}` → 返回当前用户可访问的工作空间、成员与项目摘要。  
  - `POST /api/v1/workspaces/{id}/projects` → 初始化项目并生成默认目录。  
- **数据模型**  
  - `workspaces(id, name, plan, status, created_by, created_at, updated_at)`  
  - `workspace_members(workspace_id, user_id, role)`（role: owner/member）。  
  - `roles(id, workspace_id, key, name, description, is_system, created_at, updated_at)`：工作空间作用域角色定义，`key` 在同一 workspace 内唯一。  
  - `role_permissions(role_id, operation, created_at)`：角色可执行操作（固定集合包含 `data_import`、`training_launch`、`deployment_manage`、`inference_use`、`evaluation_view`、`approval_manage`，后续可扩展）。  
  - `workspace_member_roles(workspace_id, user_id, role_id, assigned_at)`：成员与角色的多对多关系，owner 默认绑定 `workspace-admin` 系统角色。  
  - `projects(id, workspace_id, name, status, created_at, updated_at)`。  
- **默认目录结构**：在 `storage/workspaces/{workspace_id}/projects/{project_id}/` 下创建 `docs/`, `datasets/`, `pipelines/`，同时在 `docs/` 写入 `README.md` 占位文档。
- **权限与审计**：所有接口要求 Bearer Token 鉴权；服务层会校验成员关系并调用 `AuditLogRepository` 记录 `workspace.created`、`workspace.updated`、`workspace.project.created` 等事件。
- **权限扩展**：引入 `PermissionService` 依据 `roles`→`role_permissions`→`workspace_member_roles` 计算操作集。更新工作空间、创建项目等敏感操作需具备 `approval_manage` 或 `training_launch` 权限；若校验失败，将写入 `audit_logs` 事件 `authz.workspace.denied`，保存工作空间与失败原因。
- **异常处理**：名称冲突、项目重复等情况分别抛出 `WorkspaceConflictError`、`ProjectConflictError`，API 层转为 409；未加入成员访问返回 403。



## Post-Review Follow-ups

- 2025-10-29: Story 1.1 - Ensure verification attempt counters increment on invalid codes to enforce `attempt_limit`.
- TODO: 在运维手册中补充角色管理操作流程、回滚指引以及批量导入默认角色脚本方案。

## 10. RoleManagementService（Story 1.3 新增）
- **职责**：提供工作空间角色矩阵查询、角色创建/更新、成员角色维护等高级操作，保证权限与审计一致性。
- **接口与流程**  
  - `GET /api/v1/workspaces/{id}/roles`：聚合返回角色列表（含操作枚举）、成员角色分配以及可选权限集合。
  - `POST /api/v1/workspaces/{id}/roles`：创建自定义角色（系统角色只读），自动生成唯一 key 并校验操作集合法性。
  - `PATCH /api/v1/workspaces/{id}/roles/{roleId}`：更新角色名称、描述及权限。系统角色仅允许调整描述，禁止修改名称与操作集合。
  - `POST /api/v1/workspaces/{id}/members/{memberId}/roles`：重置成员角色集合，实时生效并触发审计。
- **权限控制**：所有变更操作依赖 `PermissionService` 校验 `approval_manage` 权限；普通成员仅能读取矩阵。
- **审计事件**：角色生命周期与成员授权分别写入 `workspace.role.created`、`workspace.role.updated`、`workspace.role.assignment`，payload 包含角色/成员 ID 与前后差异，便于治理审计。
- **前端支持**：`WorkspacesPage` 增设角色矩阵视图、角色编辑表单、成员勾选；通过 `workspaceApi` 调用上述接口并提供即时反馈。
