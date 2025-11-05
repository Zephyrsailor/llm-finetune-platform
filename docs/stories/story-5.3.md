<!-- requirements_context_summary:start -->
## 需求背景与约束摘要
- Epic 5 Story 5.3 要求交付统一的 API/SDK 接入层，为外部/内部应用提供标准化推理调用、鉴权与日志审计能力。[来源: docs/epics.md:300-308]
- PRD 的“部署与服务平台”章节明确平台需输出可复用的 API/SDK，并覆盖鉴权、限流、调用统计与日志审计，支撑业务系统快速集成。[来源: docs/PRD.md:40-48]
- 产品简报强调基于 vLLM 的部署平台必须对外提供 API/SDK，并在后续阶段沉淀为可分发的 SDK 资产以扩展合作伙伴生态。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:31-44,144-145]
- 平台架构采用 FastAPI 单体服务 + Celery + vLLM，要求所有外部接口遵循统一的 OpenAPI/安全策略（JWT、RBAC、审计日志、速率限制）。[来源: docs/architecture.md:5-113,163-182]
- 技术决策文件强调“API Contract First”与 Domain Service + Repository 模式，需与现有 DeploymentService/ModelRegistryService 对齐，避免重复实现基础能力。[来源: docs/technical-decisions.md:10-29; docs/tech-specs/platform-core-modules.md:1-200]
<!-- requirements_context_summary:end -->

<!-- structure_alignment_summary:start -->
## 结构对齐与历史经验
- Story 5.1/5.2 已提供模型注册与部署流水线，API 层需复用 `ModelRegistryService`、`DeploymentService` 的权限与审计模式，确保 SDK 可获取稳定的推理入口与凭证。[来源: docs/stories/story-5.1.md:1-140; docs/stories/story-5.2.md:1-157]
- 既有训练/评估/部署模块均采用 REST + Pydantic Schema + Pytest 套件；API/SDK 接入层应沿用同一编码规范、异常处理与测试策略，便于维护一致性。[来源: backend/app/api; docs/Python编码规范与风格指南.md]
- Observability 方案依赖审计日志与统一日志流（Training Log、部署事件）；推理调用日志需落在同一监控/审计通道，方便后续 Story 5.4 的运行监控复用。[来源: docs/architecture.md:79-113; docs/stories/story-4.4.md:1-140]
- 平台目录结构与模块划分已在 `docs/architecture.md`、`docs/tech-specs/platform-core-modules.md` 中确立，SDK 与示例需放置在约定的 `sdk/` 或 `examples/` 目录，遵循统一的包命名与构建流程。[来源: docs/architecture.md:37-55]
<!-- structure_alignment_summary:end -->

<!-- story_header:start -->
# Story 5.3: API/SDK 接入层

Status: Done
<!-- story_header:end -->

## Story

作为应用开发者，  
我希望获得标准化的 API 与 SDK，  
以便在业务系统中快速集成微调模型服务并满足运维要求。

<!-- acceptance_criteria:start -->
## Acceptance Criteria
1. 提供 REST/gRPC API 与 Python/JavaScript SDK 示例：API 文档涵盖模型列表、推理请求、批量调用、状态查询与错误码；SDK 支持快速初始化、凭证管理与示例调用脚本。[来源: docs/epics.md:300-308; docs/PRD.md:40-48]
2. 推理接口必须接入鉴权（JWT + 工作空间权限）、限流与配额控制，并在开发者指南中说明配置方法；违反配额时返回结构化错误并写入审计日志。[来源: docs/epics.md:300-308; docs/architecture.md:163-182]
3. 推理调用日志（成功/失败、延迟、请求量）写入监控系统并关联工作空间/项目，供 Story 5.4 的监控与计费使用；同时提供导出或查询接口给运维人员复查。[来源: docs/epics.md:300-308; docs/architecture.md:79-113]
<!-- acceptance_criteria:end -->

<!-- tasks_subtasks:start -->
## Tasks / Subtasks

- [x] 后端：推理 API 网关与服务编排（AC1-AC3）
  - [x] 新增 `InferenceService`/`InferenceRepository`，整合部署模块提供的 endpoint/token，暴露 REST `POST /api/v1/inference`、`GET /api/v1/inference/jobs/{id}` 与 gRPC 服务，遵循 Domain Service + Repository 模式。[来源: docs/tech-specs/platform-core-modules.md:1-200; docs/stories/story-5.2.md:1-157]
  - [x] 实现限流与配额控制：集成 Redis 计数器或 FastAPI 依赖注入策略，按工作空间与 API key 统计调用次数/并发，异常时返回标准错误码并写审计事件 `inference.rate_limited`。[来源: docs/architecture.md:163-182]
  - [x] 调用日志落地（数据库或日志流）并推送至监控：记录请求 ID、workspace、model_version、延迟、响应状态，提供 `GET /api/v1/inference/logs`（分页/过滤）接口，供 Story 5.4 复用。[来源: docs/epics.md:300-308; docs/architecture.md:79-113]
- [x] 客户端 SDK 与示例（AC1-AC2）
  - [x] 设计 Python SDK（`sdk/python/llmft_client`）与 JS SDK（`sdk/js/llmft-client`），封装鉴权、重试、批量调用、流式/同步推理，附带 README 与 quickstart 示例。[来源: docs/product-brief-llm-finetune-platform-2025-10-23.md:35-44,144-145]
  - [x] 自动生成/同步 OpenAPI 文档至 `docs/api-reference.md`，并提供代码示例展示请求/响应结构、错误处理、配额提示。[来源: docs/technical-decisions.md:10-29]
  - [x] 集成 CI 或脚本对 SDK 进行基础测试（unit + smoke），并确保与后端契约（OpenAPI/gRPC proto）保持一致，必要时加入 schema 校验。
- [x] 安全、监控与文档交付（AC2-AC3）
  - [x] 扩展鉴权模块：生成推理专用 API key/Token 管理接口（创建、吊销、配额配置），记录 `api_key.created/revoked` 审计事件并对接 RBAC。[来源: docs/architecture.md:163-182]
  - [x] 文档化限流/配额/日志策略，更新运维手册与开发者指南；在控制台提供入口（或占位）展示剩余配额与调用统计。[来源: docs/PRD.md:45-48]
  - [x] 编写后端 Pytest（API +限流+日志）、gRPC 集成测试，以及 SDK 端到端示例测试，确保日志与监控指标写入成功。
<!-- tasks_subtasks:end -->

## Dev Notes

- 推理 API 应复用 DeploymentService 暴露的活跃 endpoint/token，必要时引入内部负载均衡或路由层（例如通过配置 `InferenceRouter` 从数据库读取流量权重）。实现时需注意部署环境变更的实时性，可结合 Redis pub/sub 或定时刷新缓存。[来源: docs/stories/story-5.2.md:1-157]
- 鉴权/限流统一使用 PermissionService 与新的 API key 模块，遵循现有 RBAC + AuditLog 规范；配额与速率限制建议存储在 `workspace_settings` 或新表，便于 Story 5.4 监控继承。[来源: docs/architecture.md:163-182]
- 调用日志可沿用 Observability 模式（JSON 日志 + SSE/日志表），并将关键字段（workspace、project、model_version、latency、token_usage）写入数据库或 Redis Stream，供监控仪表盘消费。[来源: docs/architecture.md:79-113]
- SDK 需遵循仓库编码规范：Python 采用 Pydantic/requests 或 httpx，JS 采用 Fetch API/TanStack Query 封装；注意包名、打包脚本与发布流程（可先提供本地安装指南）。[来源: docs/Python编码规范与风格指南.md; docs/architecture.md:37-55]

### Project Structure Notes

- 后端接口预计位于 `backend/app/api/inference.py`、服务层 `backend/app/services/inference.py`、任务或限流组件可置于 `backend/app/core/`。数据库迁移需新增 `inference_calls` 或相关统计表。
- SDK 目录建议新增 `sdk/` 顶层文件夹，子目录 `python/`、`js/` 附带 package 配置、文档与示例。示例应用可放在 `examples/inference/`。
- 文档更新：在 `docs/api-reference.md`（若缺则创建）与 `docs/tech-specs/` 下新增或扩展章节描述推理 API/SDK、鉴权流程、限流策略。

### References

- docs/epics.md:300-308
- docs/PRD.md:40-48
- docs/product-brief-llm-finetune-platform-2025-10-23.md:31-44,144-145
- docs/architecture.md:5-113,163-182
- docs/technical-decisions.md:10-29
- docs/stories/story-5.1.md:1-140
- docs/stories/story-5.2.md:1-157

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Codex GPT-5（遵循 Python 编码规范）

### Debug Log References

- backend/app/services/inference.py：重构限流事务并记录 `inference.rate_limited` 审计事件，确保失败调用落入 `inference_calls`。  
- backend/app/grpc/inference_server.py：修复 gRPC 调用身份解析与参数校验，统一抛错信息。  
- backend/tests/test_inference.py：扩展限流断言并新增 gRPC handler 单元测试；使用 `pytest.importorskip` 兼容缺失的 `protobuf` 依赖。  
- frontend/src/lib/api.ts、frontend/src/app/inference/InferenceConsolePage.tsx：新增推理控制台页面与 API 客户端，涵盖调用统计、调试与 API Key 管理。  
- docs/tech-specs/platform-core-modules.md、docs/ux-specification.md、docs/api-reference.md：更新推理模块职责、导航结构与接口说明，并记录新依赖。  
- 测试：`PYTHONPATH=. backend/venv/bin/python -m pytest backend/tests/test_inference.py -q`；`pnpm vitest run src/app/inference/__tests__/InferenceConsolePage.test.tsx`。

### Completion Notes List

- 满足 AC1：REST/gRPC 接口与 Python/JS SDK 均可调用推理服务，SDK README 给出快速示例。  
- 满足 AC2：JWT/API Key 双通道鉴权、限流/配额与 429 错误写入审计日志，前端控制台可视化剩余配额。  
- 满足 AC3：调用日志落地并通过控制台展示，文档同步给出查询与告警接入指引。

### File List

- backend/app/services/inference.py
- backend/app/grpc/inference_server.py
- backend/tests/test_inference.py
- backend/pyproject.toml
- frontend/src/lib/api.ts
- frontend/src/app/inference/InferenceConsolePage.tsx
- frontend/src/app/inference/__tests__/InferenceConsolePage.test.tsx
- frontend/src/app/router.tsx
- docs/tech-specs/platform-core-modules.md
- docs/ux-specification.md
- docs/api-reference.md
- docs/stories/story-5.3.md

### Change Log

- 构建推理限流与日志记录（RateLimit 审计 + gRPC handler）并完善测试覆盖。  
- 新增推理控制台前端页面与 API 客户端，补充 SDK/文档与导航指引。
