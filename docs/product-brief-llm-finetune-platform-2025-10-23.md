# Product Brief: llm-finetune-platform

**Date:** 2025-10-23  
**Author:** zephyr
**Status:** Draft for PM Review

---

## Executive Summary

- **产品定位**：构建面向企业的“大语言模型微调一站式平台”，覆盖数据处理、训练执行、模型部署、效果评估与治理协作全链路。  
- **核心价值**：让缺乏深度模型经验的企业客户也能快速获得可复用的微调能力，同时满足我们内部“边学边用”的孵化需求。  
- **差异化**：以“质量守护 + 安全可控 + 可视化评估”作为平台基准，首期即提供数据脱敏、训练回滚、评估报告三大硬核能力，为后续商业化合作奠定基础。

---

## Problem Statement

当前企业在引入大模型微调时面临以下痛点，我们内部也缺乏能够复制交付的实践平台：

- **缺少成套流水线**：现有开源工具（LoRA/QLoRA/DoRA、LlamaFactory 等）过于专业、碎片化，企业团队难以独立完成“数据→训练→部署→评估”闭环。  
- **训练风险高**：灾难性遗忘、指标劣化、模型性能难以回溯，导致客户难以信任微调结果。  
- **数据安全担忧**：企业对私有数据的上传、脱敏、留痕审计有严格要求，缺乏安全可控的处理环境。  
- **价值难以量化**：缺少标准化评估与可视化报告，业务方无法快速判断微调后的收益，合作推进效率低。  
- **内部经验薄弱**：我们需要一套可反复实践的平台来沉淀方法论，同时对外输出解决方案、开展商业合作。

---

## Proposed Solution

打造“llm-finetune-platform”平台，形成可配置、可复用、可对外交付的微调能力，核心模块包括：

1. **数据与语料工作台**：支持多源数据接入、清洗、质量控制、格式标准化、增强与版本管理，满足企业最小合规需求。  
2. **微调执行引擎**：提供 LoRA/QLoRA/DoRA 等参数高效方案模板，内置向导式配置、实时监控、断点续训、回滚能力。  
3. **部署与服务平台（基于 vLLM）**：一键部署训练前/后的模型，支持多版本管理、灰度发布、API/SDK 输出与性能监控。  
4. **评估与监控中心**：自动对比训练前后指标，输出图表化报告，并记录历史评估，支持业务验证与复盘。  
5. **横向治理与协作**：流程看板、权限管理、操作审计，支撑跨角色协同与后续合规拓展。

---

## Target Users

### Primary User Segment

- 企业 AI/数据团队负责人及工程师，具备一定数据/模型基础，但缺少成熟的微调平台，希望通过外部合作快速落地专属模型。  
- 应用场景集中于客服问答、内容生成、知识检索、金融风控等对文本质量要求高的行业。

### Secondary User Segment

- 我们内部的解决方案架构师、交付团队：需要统一工具链来打磨方法论、积累复用资产。  
- 战略合作伙伴（云厂商、系统集成商）：通过平台 API/服务对接，为其客户提供微调能力。

---

## Goals and Success Metrics

### Business Objectives

- 在 6 个月内完成平台 MVP 上线，并交付 ≥2 家 PoC 客户，形成可展示案例。  
- 新客户从需求确认到模型上线的周期较人工方案缩短 50%。  
- 平台每次微调项目可形成结构化知识沉淀，累计 10+ 份可复用模板。

### User Success Metrics

- 首位外部客户在 2 周内完成“数据准备→训练→评估→部署”的闭环。  
- 训练成功率（无重大回滚）≥ 90%，核心指标较基础模型平均提升 ≥ 15%。  
- 平台自带评估报告可被业务方直接引用在决策材料中（满意度问卷 ≥ 4/5）。

### Key Performance Indicators (KPIs)

- 平台累计上线的微调模型数量。  
- 每次训练的成功率、回滚次数、质量告警数。  
- 客户续费率与追加合作机会数。  
- 平均部署延迟、推理成本（token 成本）等运营指标。

---

## Strategic Alignment and Financial Impact

### Financial Impact

- 形成标准化微调解决方案，支撑服务化营收；每个客户项目可收取平台订阅费 + 训练/部署资源费。  
- 通过缩短交付周期与降低人力投入，提高交付毛利率约 10%-15%。  
- 为 SaaS 化定价打基础，逐步形成长期 ARR。

### Company Objectives Alignment

- 支撑公司“AI 服务化 + 垂直行业解决方案”战略，构建核心竞争力。  
- 帮助销售团队在谈判中展示可视化能力样板，提升成单率。

### Strategic Initiatives

- 搭建“数据→训练→部署→评估”全链路标准流程。  
- 建立合作伙伴生态（GPU 云、系统集成商），形成联合解决方案。  
- 推动内部知识库建设，沉淀最佳实践与行业模板。

---

## MVP Scope

### Core Features (Must Have)

- 数据工作台：多源数据上传、基础清洗/脱敏、质量指标面板、JSONL 一键转换。  
- 训练引擎：LoRA/QLoRA/DoRA 模板、向导式配置、实时监控、快照回滚、训练日志留存。  
- 评估中心：标准对比测试集、自动评估脚本、图表化报告、历史记录。  
- 部署平台：基于 vLLM 的模型托管、版本切换、API/SDK 输出、基础性能监控。  
- 流程看板与权限：展示流程状态、基础工作空间权限与操作日志。

### Out of Scope for MVP

- RLHF、RLAIF 等复杂训练形态。  
- 自动化超参调优、批量实验编排。  
- BYO GPU/K8s 资源调度与弹性计费。  
- 多租户细粒度权限、合规审计资产。  
- 完整的人工标注平台。

### MVP Success Criteria

- 完成至少 1 个真实客户或内部样板项目的端到端交付。  
- 平台三大关键能力（数据脱敏、训练回滚、评估报告）全部可用并被客户认可。  
- 用户可在无人工介入的情况下，通过平台完成一次标准微调流程。

---

## Post-MVP Vision

### Phase 2 Features

- 接入自带 GPU/K8s 或多云资源池，实现弹性调度与成本追踪。  
- 发布引导式“微调操作向导”与行业模板库。  
- 扩展多角色协同（评估标注、业务审批）与工单流程。  
- 增加在线评估、长周期回归监控、自动化优化建议。

### Long-term Vision

- 建立“微调能力即服务”（Fine-tuning as a Service）生态，开放 API 供合作伙伴调用。  
- 形成行业化解决方案（金融、教育、制造等）并结合行业知识库。  
- 接入自动自愈策略，结合反馈数据实现持续优化。

### Expansion Opportunities

- 与云厂商联合推出联合解决方案或 Marketplace 产品。  
- 推出一站式咨询 + 托管服务，实现项目制 + SaaS 的混合商业模式。  
- 将平台能力下沉为 SDK，供企业自建内部平台时复用。

---

## Technical Considerations

### Platform Requirements

- Web 管理控制台 + API 接口，首期使用平台账号体系（SSO 作为后续增强）。  
- GPU 训练与推理资源统一调度，最小配置确保 2-4 卡 A100/4090。  
- 数据与模型 artefacts 先落在本地文件系统约定目录，预留迁移至 S3/OSS；向量检索按需启用 FAISS/Milvus。  
- 日志与审计通过后端日志流 + 平台“Training Log” 面板呈现实时状态，后续再评估接入 Prometheus/Grafana。

### Technology Preferences

- 训练框架：PyTorch + HuggingFace Transformers + PEFT。  
- 平台后端：Python/FastAPI 单体服务，任务编排使用 Celery + Redis。  
- 前端：React + Vite + Tailwind CSS + shadcn/ui。  
- 推理：vLLM 为主引擎，预留 Triton/KServe 集成。  
- 数据处理：Pandas/Polars + 内置审核规则引擎。

### Architecture Considerations

- 一期采用“FastAPI 单体 + Celery 任务”架构，模块划分为数据/训练/评估/部署/治理，避免过早拆分微服务。  
- 使用 Docker Compose 管理前后端、Celery、Redis、Postgres、vLLM 等组件；后续再考虑 Kubernetes。  
- 数据安全：文件系统权限 + 可选加密，接口全程 HTTPS，工作空间级隔离。  
- 可扩展性：为未来接入外部模型仓库、CI/CD 流水线预留插件接口与 API。

---

## Constraints and Assumptions

### Constraints

- GPU 资源有限，需要与内部项目共享，短期内以云租赁补足峰值。  
- 团队人力有限，前端/后端/训练工程师需兼顾多模块开发。  
- 缺乏成熟的标注团队，需要与外部合作或使用半自动方案。

### Key Assumptions

- 目标客户具备可用于微调的文本或对话数据，并愿意按照平台要求提供。  
- 客户能接受通过云环境完成训练，或愿意在可控的私有部署环境运行。  
- 市场对标准化微调平台的付费意愿与 ROI 预期保持增长。

---

## Risks and Open Questions

### Key Risks

- 数据安全事件或合规缺陷可能影响客户信任与合作推进。  
- 训练效果不达标，导致客户无法感知价值或项目延期。  
- 资源成本过高，影响盈利能力或报价竞争力。

### Open Questions

- 定价模型如何设计（订阅 vs 项目制 vs 混合）？  
- 对外输出时是否需要支持客户自有 GPU 环境？上线优先级如何？  
- 是否需要引入第三方评估/标注伙伴？合作模式是什么？

### Areas Needing Further Research

- 不同规模模型（7B/14B/70B）在 DoRA/QLoRA 下的性能与成本评估。  
- 行业客户的合规要求（金融、医疗等）及数据脱敏策略。  
- 训练质量守护指标的阈值设置与自动化回滚策略最佳实践。

---

## Appendices

### A. Research Summary

- 参考《大语言模型微调实施方案》（README），确认数据处理流程（数据清洗→质量控制→格式标准化→数据增强→存储）作为数据模块基线。  
- 汇总头脑风暴结果（2025-10-23），识别三大即时痛点：数据安全流程、训练质量守护、评估可视化。  
- 市场调研反馈：企业客户普遍希望“即插即用、效果可见、风险可控”的平台化方案。

### B. Stakeholder Input

- 内部需求方（解决方案团队）强调需要边实践边沉淀，要求平台具备知识复用与对外演示能力。  
- 业务拓展团队期待通过平台与客户谈判时展示 PoC 能力，缩短签约周期。

### C. References

- 《大语言模型微调实施方案》项目 README  
- Brainstorming Session Results（docs/brainstorming-session-results-2025-10-23.md）  
- LoRA/QLoRA/DoRA 相关最新技术论文与官方实现文档  
- vLLM 官方文档与性能基准

---

_This Product Brief serves as the foundational input for Product Requirements Document (PRD) creation._

_Next Steps: Handoff to Product Manager for PRD development using the `workflow prd` command._
