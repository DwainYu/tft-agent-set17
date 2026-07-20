# 设计决策记录 — TFT Agent Set 17

> 本文档记录项目关键技术决策，包含背景、备选方案分析、最终选择及回滚条件。
> 格式参考 [ADR (Architecture Decision Records)](https://adr.github.io/)。

---

## DD-001: Agent 框架选型 — LangGraph

### 背景

TFT Agent 需要一个能够编排多步推理、工具调用、记忆管理的 Agent 框架。Agent 需要处理用户自然语言查询，经过意图识别 → 实体抽取 → 工具调度 → 结果组装的流程，且需要支持有条件分支和循环的复杂工作流。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **LangGraph** | 原生支持有状态图、循环、条件分支；LangChain 生态深度集成；活跃的社区和文档 | 学习曲线较陡；与 LangChain 耦合较深 |
| **AutoGen (Microsoft)** | 多 Agent 对话能力强；灵活的对话模式 | 面向多 Agent 对话而非工具编排；状态管理弱；迭代慢 |
| **CrewAI** | 上手简单；角色定义直观 | 灵活性低；不适合复杂工作流；社区小；缺乏精细的状态控制 |

### 决策

**选择 LangGraph**。理由：
1. TFT Agent 需要精细的状态管理（对话上下文 + 中间推理结果），LangGraph 的 `StateGraph` 和 `Checkpointer` 天然适配
2. 工具调度是核心需求，LangGraph 的 `ToolNode` 提供原生支持
3. 未来接入 LangSmith 追踪零成本
4. 支持流式输出，可配合 SSE 实现实时推送

### 回滚条件

- LangGraph 项目停止维护或长期无更新（> 6 个月）
- 性能瓶颈无法通过优化解决
- 框架限制导致无法实现关键功能（如并行工具调用）

---

## DD-002: 向量数据库选型 — Milvus

### 背景

系统需要将 TFT 对局数据、阵容描述、棋子特征等非结构化文本向量化后存储，支持语义检索。要求支持高吞吐写入（数据采集管线批量嵌入）和低延迟查询（在线 RAG 检索）。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Milvus** | 开源可自托管；高性能（C++ 底层）；支持多种索引（IVF_FLAT, HNSW, DiskANN）；丰富的过滤条件 | 部署复杂（依赖 etcd + MinIO）；资源占用较高 |
| **Pinecone** | 全托管免运维；简单易用 | 闭源且锁定供应商；按量计费成本高；不支持自托管；数据出境问题 |
| **Weaviate** | GraphQL API 友好；内置模块化向量化 | 性能略低于 Milvus；大集合下内存占用高；社区较小 |

### 决策

**选择 Milvus**。理由：
1. 自托管保证数据主权，无供应商锁定
2. 高性能适合批量嵌入写入 + 低延迟在线查询场景
3. 开源免费，长期成本可控
4. 与 LangChain/LlamaIndex 有成熟的集成方案
5. 开发环境可使用 Milvus Lite（单文件模式），降低门槛

### 回滚条件

- Milvus 运维成本过高，团队无法承受
- 出现严重的数据一致性或性能问题
- 需要 GraphQL 查询能力且 Milvus 无法满足

---

## DD-003: 图数据库选型 — Neo4j

### 背景

TFT 中棋子、装备、Augment 之间存在丰富的协同/克制关系。需要图数据库建模和查询这些关系，支持"哪些装备和某棋子协同最好"、"当前阵容缺少什么羁绊"等图查询。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Neo4j** | 行业标准图数据库；Cypher 查询语言强大且易学；社区活跃、文档丰富；LangChain 原生集成 | 企业版收费；大规模数据需要调优 |
| **Amazon Neptune** | 全托管免运维；AWS 生态集成好 | 锁定 AWS；闭源；成本高；Gremlin/SPARQL 学习成本高 |
| **ArangoDB** | 多模型（文档+图+KV）；灵活 | 图查询性能不如专用图数据库；社区较小；复杂图算法支持有限 |

### 决策

**选择 Neo4j**。理由：
1. Cypher 查询语言直观，适合"棋子-装备-羁绊"关系建模
2. LangChain 提供 `Neo4jGraph` 和 `GraphCypherQAChain`，集成零成本
3. Neo4j Community Edition 满足当前规模需求
4. 丰富的可视化工具（Neo4j Browser, Bloom）便于调试

### 回滚条件

- 数据规模超出 Neo4j Community Edition 能力（> 数十亿边）
- 需要多模型（文档+图）统一存储
- Neo4j 许可变更不利于项目

---

## DD-004: LLM 推理引擎选型 — vLLM

### 背景

系统需要部署 Qwen2.5-14B-Instruct-AWQ 模型，提供低延迟、高吞吐的在线推理服务。Agent 每次对话可能涉及多轮 LLM 调用（意图识别、工具参数生成、结果总结），对推理效率要求高。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **vLLM** | PagedAttention 优化 KV Cache；支持 continuous batching；OpenAI 兼容 API；社区最活跃 | 仅支持 NVIDIA GPU；AWQ 量化支持有限 |
| **SGLang** | RadixAttention 前缀缓存；结构化输出快 | 社区较小；生态不如 vLLM 成熟 |
| **TGI (Text Generation Inference)** | HuggingFace 官方出品；Flash Attention | 配置复杂；文档不够友好；更新频率低 |

### 决策

**选择 vLLM**。理由：
1. PagedAttention 显著提升显存利用率，相同 GPU 可服务更多并发请求
2. OpenAI 兼容 API 降低集成成本（LangChain/LangGraph 直接使用 `ChatOpenAI`）
3. 对 AWQ 量化模型有良好支持
4. 社区最活跃，问题容易找到解决方案
5. 支持 tensor parallelism，方便后续扩展

### 回滚条件

- vLLM 在 AWQ 模型上存在无法解决的 bug
- SGLang 的结构化输出能力对 Agent 工具有显著优势
- 需要支持非 NVIDIA 硬件（AMD / Intel GPU）

---

## DD-005: Web 框架选型 — FastAPI

### 背景

后端 API 需要支持 REST 端点（CRUD、认证）、SSE 流式推送（Agent 对话）、WebSocket（未来实时对战数据）、异步 I/O（高并发爬虫和推理请求）。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **FastAPI** | 原生 async/await；自动 OpenAPI 文档；Pydantic v2 集成；类型安全；性能优秀 | 社区规模小于 Flask（但增长快） |
| **Flask** | 生态最大；简单易学；灵活 | 默认同步（需额外配置 async）；无内置 API 文档生成；类型安全弱 |
| **Express (Node.js)** | JavaScript 全栈；生态丰富 | 不适合 CPU 密集（推理调用）；与 Python ML 生态割裂；类型安全需额外工具 |

### 决策

**选择 FastAPI**。理由：
1. 原生 async 适合 I/O 密集场景（Riot API 调用、数据库查询、vLLM 推理等待）
2. Pydantic v2 深度集成，数据验证和序列化零成本
3. 自动生成 OpenAPI 文档，前后端协作效率高
4. SSE 支持简单（`StreamingResponse`），配合 LangGraph 流式输出天然契合
5. Python 生态与 ML/AI 工具链统一

### 回滚条件

- FastAPI 出现严重安全漏洞且未及时修复
- 团队 Python 能力不足，切换到 Node.js 更高效

---

## DD-006: 数据库迁移路径 — SQLite → Postgres

### 背景

项目初期使用 SQLite 快速验证，但随着用户增长和功能复杂化（并发写入、全文搜索、JSON 查询），需要迁移到生产级关系数据库。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **SQLite → Postgres** | SQLite 开发零配置，Postgres 生产级稳定；Alembic 管理迁移；丰富的扩展（pgvector） | 需要维护两套配置；迁移需要数据导入脚本 |
| **始终使用 Postgres** | 统一技术栈；避免迁移风险 | 开发环境需要 Docker；本地开发启动慢 |
| **始终使用 SQLite** | 简单无依赖 | 不支持并发写入；无 JSONB；不适合生产 |

### 决策

**选择 SQLite (开发) → Postgres (生产) 渐进迁移**。理由：
1. Phase 1 快速迭代阶段 SQLite 零配置，降低开发门槛
2. SQLAlchemy async ORM 屏蔽底层差异，切换仅需更改连接字符串
3. Postgres 支持 pgvector，未来可替代 Milvus 用于小规模向量检索
4. Alembic 管理 schema 迁移，可控、可回滚

**迁移触发条件**: 并发写入冲突频率 > 1%/天，或用户数 > 1000，或需要全文搜索/JSONB。

### 回滚条件

- 如果 Postgres 运维成本超出预期，考虑使用托管服务（Supabase / RDS）
- 如果 SQLite WAL 模式能满足需求，推迟迁移

---

## DD-007: 实时通信选型 — SSE (Server-Sent Events)

### 背景

Agent 对话需要将 LLM 生成的 token 实时推送到前端，用户期望"打字机"效果。需要评估 SSE vs WebSocket。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **SSE (Server-Sent Events)** | 基于 HTTP，无需额外协议；自动重连；单向推送契合 LLM token 流；FastAPI `StreamingResponse` 原生支持 | 仅服务器→客户端单向；IE 不支持 |
| **WebSocket** | 双向通信；低延迟；广泛支持 | 需要额外协议升级；连接管理复杂；FastAPI 支持但不如 SSE 简洁 |

### 决策

**选择 SSE**。理由：
1. LLM token 流是 **单向** 的（服务器 → 客户端），SSE 天然适配
2. 用户输入通过 HTTP POST 发送，不需要 WebSocket 的双向通道
3. FastAPI `StreamingResponse` 实现 SSE 仅需 10 行代码
4. 浏览器 EventSource API 自动处理重连
5. 无需引入额外的 WebSocket 连接管理（心跳、断线重连逻辑）

### 回滚条件

- 需要服务器向客户端推送实时通知（如对战数据更新、排行榜变动）
- 需要双向实时通信（如多人协作编辑阵容）

---

## DD-008: 嵌入模型选型 — BGE-M3

### 背景

RAG 管线需要将 TFT 对局描述、阵容文本、攻略文章等转化为向量嵌入。文本包含中文（棋子中文名、攻略）和英文（Riot API 数据），需要多语言支持。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **BGE-M3 (BAAI)** | 多语言（100+ 语言）；多粒度（Dense + Sparse + ColBERT）；开源可自托管；中文效果优秀 | 模型较大（~2.2GB）；推理需要 GPU 或较强 CPU |
| **text-embedding-3-small/large (OpenAI)** | 简单易用；性能稳定 | 闭源 API 调用；按量计费；数据出境；无法离线使用 |
| **Cohere Embed v3** | 多语言；压缩技术好 | 闭源 API；按量计费；国内访问延迟高 |

### 决策

**选择 BGE-M3**。理由：
1. 多语言覆盖中英文，无需维护两套嵌入管线
2. 多粒度检索（Dense + Sparse + ColBERT）提升召回质量
3. 开源自托管，无数据出境问题，无 API 调用成本
4. 中文效果在同级别模型中领先
5. 可与 Milvus 配合，支持混合检索

### 回滚条件

- BGE-M3 推理延迟无法满足在线需求（> 100ms/query）
- GPU 资源不足，无法承担嵌入推理成本
- 需要更小的模型用于边缘部署

---

## DD-009: 模型量化方案 — AWQ

### 背景

Qwen2.5-14B 全精度（FP16）需要 ~28GB 显存，单张消费级 GPU 无法承载。需要通过量化降低显存占用，同时保持模型质量。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **AWQ (Activation-aware Weight Quantization)** | 4-bit 量化质量接近 FP16；vLLM 原生支持；量化速度快 | 仅支持 NVIDIA GPU |
| **GPTQ** | 广泛支持；4-bit 质量好 | 量化速度慢于 AWQ；vLLM 支持略弱 |
| **GGUF (llama.cpp)** | CPU 推理友好；跨平台 | 推理速度慢于 GPU 方案；vLLM 不支持 |

### 决策

**选择 AWQ**。理由：
1. AWQ 在 4-bit 量化下质量损失最小（perplexity 接近 FP16）
2. vLLM 对 AWQ 支持成熟（`--quantization awq`）
3. 14B AWQ 模型仅需 ~8-10GB 显存，单张 A10G/L4 可运行
4. 量化后推理速度更快（内存带宽瓶颈降低）

### 回滚条件

- AWQ 量化导致 Agent 工具调用准确率显著下降（> 5%）
- 需要 CPU 推理场景（切换到 GGUF + llama.cpp）
- 新硬件支持更好的量化方案（如 FP8 on H100）

---

## DD-010: CI/CD 平台选型 — GitHub Actions

### 背景

项目托管在 GitHub，需要 CI/CD 平台执行 lint、test、build、deploy 流程。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **GitHub Actions** | 与 GitHub 深度集成；YAML 配置简单；丰富的 Marketplace Actions；免费额度充足 | 自托管 Runner 配置略复杂 |
| **GitLab CI** | 功能全面；自托管 Runner 成熟 | 需要迁移到 GitLab；与 GitHub 集成差 |
| **Jenkins** | 灵活度最高；插件丰富 | 配置复杂（Groovy）；维护成本高；UI 老旧 |

### 决策

**选择 GitHub Actions**。理由：
1. 代码托管在 GitHub，零集成成本
2. YAML 配置声明式，易于理解和维护
3. Marketplace 提供丰富的预构建 Actions（Docker build、Helm deploy、Snyk scan）
4. 开源项目免费额度充足（无限分钟）
5. 与 Dependabot、CodeQL 等 GitHub 安全工具无缝协作

### 回滚条件

- GitHub Actions 免费额度不足
- 需要复杂的流水线编排（如多环境并行部署 + 审批流）
- 团队迁移到其他代码托管平台

---

## DD-011: 监控方案选型 — Prometheus + Grafana

### 背景

系统需要监控 API 性能、Agent 推理指标、GPU 利用率、数据库连接池等多维度指标，并支持告警。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Prometheus + Grafana** | 开源免费；K8s 原生；生态最丰富；社区活跃 | 需要自行运维；长期存储需额外方案（Thanos/VictoriaMetrics） |
| **Datadog** | 全托管；开箱即用；AI 辅助分析 | 按主机计费，成本高；数据出境；供应商锁定 |
| **New Relic** | 全栈可观测；免费层慷慨 | 功能分散；中文支持弱；部分高级功能昂贵 |

### 决策

**选择 Prometheus + Grafana**。理由：
1. 开源免费，无供应商锁定
2. K8s 原生支持（ServiceMonitor / PodMonitor）
3. Grafana 面板高度可定制，可共享 JSON 模板
4. vLLM 原生暴露 Prometheus 指标
5. AlertManager 灵活配置告警路由
6. 与 LangSmith 互补：Prometheus 监控系统指标，LangSmith 监控 LLM 调用链

### 回滚条件

- 运维成本超出团队承受能力
- 需要 APM（应用性能监控）级别的代码追踪
- 多区域部署需要全局视图（考虑 Thanos）

---

## DD-012: LLM 可观测性选型 — LangSmith

### 背景

Agent 系统涉及多步 LLM 调用（意图识别、工具参数生成、结果总结），需要追踪每一步的输入/输出、延迟、token 消耗，便于调试和优化。

### 备选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **LangSmith** | LangChain/LangGraph 原生集成（设置环境变量即可）；Trace 可视化优秀；支持 Evaluation | 依赖 LangChain 生态；部分高级功能收费 |
| **Arize Phoenix** | 开源；支持多种框架；本地部署 | LangGraph 集成不如 LangSmith 深；社区较小 |
| **自建追踪** | 完全可控；定制化强 | 开发成本高；需自建 UI；维护成本大 |

### 决策

**选择 LangSmith**。理由：
1. 项目已选择 LangGraph 作为 Agent 框架，LangSmith 零代码集成（`LANGCHAIN_TRACING_V2=true`）
2. Trace 可视化直观展示 Agent 执行图，便于定位性能瓶颈和错误
3. 内置 Evaluation 框架，可管理 prompt 版本和评估数据集
4. 免费层满足开发和小规模使用需求

### 回滚条件

- LangSmith 收费策略变更，成本不可接受
- LangSmith 服务不稳定，影响开发效率
- 需要完全的数据自主权（切换到 Arize Phoenix 或自建）
- 脱离 LangChain 生态（切换到其他 Agent 框架）
