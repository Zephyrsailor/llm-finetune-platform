# llm-finetune-platform - Epic Breakdown

**Author:** zephyr  
**Date:** 2025-10-23  
**Project Level:** 3  
**Target Scale:** 企业级多租户 SaaS 平台（Level 3 复杂系统）

---

## Overview

This document provides the detailed epic breakdown for llm-finetune-platform, expanding on the high-level epic list in the [PRD](./PRD.md).

Each epic includes:

- Expanded goal and value proposition
- Complete story breakdown with user stories
- Acceptance criteria for each story
- Story sequencing and dependencies

**Epic Sequencing Principles:**

- Epic 1 establishes foundational基础设施和访问控制  
- Subsequent epics build progressively, each delivering significant end-to-end value  
- Stories within epics are vertically sliced and sequentially ordered  
- No forward dependencies - each story builds only on previous work

---

## Epic 1：平台基础与访问控制

**Expanded Goal**  
构建平台登录、工作空间与权限基础，使内部与客户团队能够安全访问，并提供统一的项目总览。

**Story Breakdown**

**Story [1.1]: 基础登录与账号管理**  
As a platform administrator,  
I want users to 使用邮箱/密码登录并安全维护会话,  
So that 团队成员可以在受控环境下访问平台。

**Acceptance Criteria:**  
1. 支持邮箱+密码注册、登录、退出，密码需满足最小长度与复杂度要求。  
2. 登录流程包含验证码或邮箱验证，失败时返回明确错误并记录审计日志。  
3. Session/Token 管理（JWT 或服务器会话）具备过期策略与手动注销；提供“忘记密码/重置”流程。  
4. 基础审计字段（最后登录时间、来源 IP）可在管理员界面查看。

**Prerequisites:** 无

**Story [1.2]: 工作空间与项目创建流程**  
As a platform administrator,  
I want to create工作空间并初始化项目模板,  
So that internal and client teams can在隔离环境中启动微调项目。

**Acceptance Criteria:**  
1. 支持创建/编辑/归档工作空间；项目需关联到具体工作空间。  
2. 新项目创建时自动生成默认目录结构及占位文档。  
3. 权限校验确保非成员无法访问对应工作空间。

**Prerequisites:** Story 1.1

**Story [1.3]: 角色与权限矩阵**  
As a security officer,  
I want to 分配角色（管理员、数据、训练、运维、业务审阅）,  
So that 关键操作仅向被授权成员开放。

**Acceptance Criteria:**  
1. 角色权限涵盖数据导入、训练启动、部署发布、评估查看等关键操作。  
2. UI 提供角色管理界面，可自定义角色与授权。  
3. 权限变更即时生效并记录审计日志。

**Prerequisites:** Story 1.2

**Story [1.4]: 项目总览仪表盘（基础版）**  
As a project sponsor,  
I want to 查看项目状态概览,  
So that 可快速了解数据、训练、评估、部署环节进度。

**Acceptance Criteria:**  
1. 仪表盘展示各环节状态（未启动/进行中/完成）与负责人。  
2. 提供关键指标占位（后续阶段补充数据）。  
3. 支持按工作空间过滤与访问权限一致。

**Prerequisites:** Story 1.3

## Epic 2：数据与语料工作台 MVP

**Expanded Goal**  
让用户能够导入、清洗、评估与管理训练数据，确保数据质量与安全可控。

**Story Breakdown**

**Story [2.1]: 多源数据导入与元数据登记**  
As a data engineer,  
I want to 上传文件或配置对象存储路径导入语料,  
So that 平台能接收企业的多样化数据来源。

**Acceptance Criteria:**  
1. 支持 CSV/JSON/JSONL/Parquet/ZIP 上传及 OSS/S3 路径引用。  
2. 入库时记录来源、上传者、时间戳、数据类型等元数据。  
3. 大于阈值的文件支持分块断点续传并返回进度。

**Prerequisites:** Story 1.4

**Story [2.2]: 数据清洗与脱敏流水线**  
As a compliance officer,  
I want to 配置去重、噪声过滤与敏感词/PII 脱敏策略,  
So that 数据在训练前满足合规要求。

**Acceptance Criteria:**  
1. 支持模板化清洗规则，可针对不同数据集启用/禁用。  
2. 清洗结果提供统计（删除记录数、脱敏字段数、错误日志）。  
3. 脱敏规则可导出用于审计。

**Prerequisites:** Story 2.1

**Story [2.3]: 数据质量评估仪表盘**  
As a data scientist,  
I want to 查看困惑度、长度分布、重复率等质量指标,  
So that 能判断数据是否可用于微调。

**Acceptance Criteria:**  
1. 质量评估自动在清洗后执行，并输出评分与建议。  
2. 仪表盘支持 drill-down 查看异常样本。  
3. 指标与原始数据版本关联，可追踪历史。

**Prerequisites:** Story 2.2

**Story [2.4]: 格式标准化与版本管理**  
As a ML engineer,  
I want to 将清洗后的数据一键转换为 JSONL/SFT/Parquet 等格式,  
So that 训练模块能直接引用标准格式。

**Acceptance Criteria:**  
1. 转换结果自动生成版本号与校验和。  
2. 支持下载与差异对比，回滚到任意历史版本。  
3. 提供 API 供训练模块按版本拉取数据。

**Prerequisites:** Story 2.3

---

## Epic 3：微调执行引擎 MVP

**Expanded Goal**  
提供参数高效训练模板、编排流程与质量守护机制，保证训练稳定可靠。

**Story Breakdown**

**Story [3.1]: 训练方案模板库**  
As a ML engineer,  
I want to 选择 LoRA/QLoRA/DoRA 模板并可调整关键参数,  
So that 在不同场景下快速配置训练。

**Acceptance Criteria:**  
1. 模板预设学习率、rank、量化策略等参数。  
2. 支持导入自定义基座模型与保存常用配置。  
3. 参数范围校验并提供最佳实践提示。

**Prerequisites:** Story 2.4

**Story [3.2]: 向导式训练编排**  
As a data scientist,  
I want to 按步骤完成模型选择、数据绑定、资源配置、超参设定,  
So that 可以低门槛地发起训练任务。

**Acceptance Criteria:**  
1. 每一步提供默认值与校验，阻止不完整配置。  
2. 支持保存草稿与复制历史任务。  
3. 启动时生成唯一任务 ID 并写入训练队列。

**Prerequisites:** Story 3.1

**Story [3.3]: 实时监控与告警**  
As an operations engineer,  
I want to 观察 loss、困惑度、显存、吞吐等指标并配置告警,  
So that 训练异常时可立即响应。

**Acceptance Criteria:**  
1. 指标实时刷新，支持自定义阈值触发邮件/消息通知。  
2. 指标数据保留，支持导出 CSV/JSON。  
3. 告警记录与任务关联，可在仪表盘查看处理进度。

**Prerequisites:** Story 3.2

**Story [3.4]: 快照、断点续训与回滚**  
As a ML engineer,  
I want 平台自动保存检查点并可手动回滚,  
So that 训练失败或指标恶化时能快速恢复。

**Acceptance Criteria:**  
1. 每 N 步或 epoch 自动保存快照，存储对应配置。  
2. 支持从指定快照继续训练，保留训练链路。  
3. 回滚后自动触发评估以验证模型质量。

**Prerequisites:** Story 3.3

**Story [3.5]: 元数据与实验管理**  
As a product analyst,  
I want 追踪训练元数据并对比实验结果,  
So that 方便复盘与优化。

**Acceptance Criteria:**  
1. 任务记录包含模型、数据版本、参数、耗时、成本。  
2. 支持在 UI 中对比两次训练指标与配置差异。  
3. 元数据可导出到知识库或 BI 工具。

**Prerequisites:** Story 3.4

---

## Epic 4：评估与报告中心 MVP

**Expanded Goal**  
提供标准化评估流水线与报告，使业务可量化微调收益并持续监控质量。

**Story Breakdown**

**Story [4.1]: 标准化评估套件**  
As a QA lead,  
I want to 选择默认测试集或上传定制样本,  
So that 训练前后均能进行统一评估。

**Acceptance Criteria:**  
1. 内置通用问答、对话、分类等模板，可按场景选择。  
2. 支持自定义测试集上传并与版本绑定。  
3. 评估任务自动关联至对应训练任务。

**Prerequisites:** Story 3.5

**Story [4.2]: 自动化评估流水线**  
As a ML engineer,  
I want 训练完成后自动运行评估并生成指标,  
So that 可以快速判断模型提升效果。

**Acceptance Criteria:**  
1. 自动计算 BLEU/ROUGE/Exact Match/困惑度等指标。  
2. 评估结果写入数据库并可通过 API 查询。  
3. 评估失败或指标退化触发告警。

**Prerequisites:** Story 4.1

**Story [4.3]: 报告生成与可视化**  
As a business owner,  
I want 获得可视化评估报告与关键案例,  
So that 可直接用于业务决策与汇报。

**Acceptance Criteria:**  
1. 报告包含指标对比图、典型提升案例及劣化样例。  
2. 支持导出 PDF/Markdown/链接分享。  
3. 报告与训练任务/模型版本双向链接。

**Prerequisites:** Story 4.2

**Story [4.4]: 反馈与复盘记录**  
As a product manager,  
I want 在报告中记录业务反馈与改进建议,  
So that 后续迭代可追踪决策依据。

**Acceptance Criteria:**  
1. 报告页面支持评论、标注 TODO、附加业务指标。  
2. 反馈记录纳入知识库，可按项目查询。  
3. 新训练任务可引用历史反馈作为改进目标。

**Prerequisites:** Story 4.3

---

## Epic 5：部署与运营监控 MVP

**Expanded Goal**  
实现从模型注册到 vLLM 部署、API 服务与性能监控的闭环，保障上线稳定。

**Story Breakdown**

**Story [5.1]: 模型注册与版本管理**  
As a release manager,  
I want 将训练好的模型注册到模型仓库并标记版本,  
So that 可以追踪上线与回滚。

**Acceptance Criteria:**  
1. 支持登记模型元数据、评估结果、部署状态。  
2. 模型版本支持“候选/生产/废弃”等状态标签。  
3. 与评估报告联动，未通过评估的模型禁止发布。

**Prerequisites:** Story 4.4

**Story [5.2]: vLLM 部署流水线**  
As an operations engineer,  
I want 一键将模型部署至 vLLM 集群,  
So that 业务方可快速调用。

**Acceptance Criteria:**  
1. 部署流程支持选择资源规格、并发参数、batch size。  
2. 上线前执行健康检查并返回 URL/密钥。  
3. 支持灰度发布与版本切换。

**Prerequisites:** Story 5.1

**Story [5.3]: API/SDK 接入层**  
As an application developer,  
I want 获得标准化 API/SDK,  
So that 可在业务系统中集成模型服务。

**Acceptance Criteria:**  
1. 提供 REST/gRPC API 与 Python/JavaScript SDK 示例。  
2. 支持鉴权、限流、配额管理，并在文档中说明。  
3. 调用日志记录至监控系统，供审计与计费使用。

**Prerequisites:** Story 5.2

**Story [5.4]: 运行监控与告警**  
As an operations engineer,  
I want 监控推理性能与用户体验指标,  
So that 发现问题可及时处理。

**Acceptance Criteria:**  
1. 仪表盘展示 QPS、延迟、错误率、Token 吞吐、资源使用。  
2. 支持设置阈值并触发告警，提供自愈建议或回滚入口。  
3. 监控数据与业务标签关联，可按客户/环境拆分。

**Prerequisites:** Story 5.3

---

## Epic 6：治理协作与知识沉淀

**Expanded Goal**  
提供协作、通知、知识复用能力，确保项目可持续优化与团队协同。

**Story Breakdown**

**Story [6.1]: 流程看板与任务指派**  
As a program manager,  
I want 在看板上分配任务并追踪进度,  
So that 团队成员责任明确。

**Acceptance Criteria:**  
1. 看板与各环节状态同步，可拖拽调整优先级。  
2. 支持指派负责人、截止日期、提醒。  
3. 与通知中心联动，更新时推送至邮件/IM。

**Prerequisites:** Story 5.4

**Story [6.2]: 多人协作评论与审批**  
As a reviewer,  
I want 在数据、训练、评估、部署页面发表评论并发起审批,  
So that 关键变更有记录与确认。

**Acceptance Criteria:**  
1. 支持 @ 成员、上传附件、引用历史记录。  
2. 审批流可配置（单人/多人），结果记录进审计日志。  
3. 评论权限遵循角色设置。

**Prerequisites:** Story 6.1

**Story [6.3]: 通知与集成中心**  
As a DevOps engineer,  
I want 将平台事件同步到企业微信/Slack/Jira,  
So that 团队可在现有工具中接收提醒。

**Acceptance Criteria:**  
1. 支持配置 Webhook/IM/Email 等多渠道。  
2. 可选择事件类型（训练完成、告警、审批、部署变更）。  
3. 发送失败有重试与回退机制。

**Prerequisites:** Story 6.2

**Story [6.4]: 知识库与模板沉淀**  
As a solutions architect,  
I want 将成功案例、配置模板、评估脚本沉淀到知识库,  
So that 后续项目可快速复用。

**Acceptance Criteria:**  
1. 支持上传文档、脚本、配置并打标签。  
2. 可从知识库一键将模板复制到新项目。  
3. 知识库内容支持版本管理与权限控制。

**Prerequisites:** Story 6.3

---

## Story Guidelines Reference

**Story Format:**

```
**Story [EPIC.N]: [Story Title]**

As a [user type],
I want [goal/desire],
So that [benefit/value].

**Acceptance Criteria:**
1. [Specific testable criterion]
2. [Another specific criterion]
3. [etc.]

**Prerequisites:** [Dependencies on previous stories, if any]
```

**Story Requirements:**

- **Vertical slices** - Complete, testable functionality delivery
- **Sequential ordering** - Logical progression within epic
- **No forward dependencies** - Only depend on previous work
- **AI-agent sized** - Completable in 2-4 hour focused session
- **Value-focused** - Integrate technical enablers into value-delivering stories

---

**For implementation:** Use the `create-story` workflow to generate individual story implementation plans from this epic breakdown.
