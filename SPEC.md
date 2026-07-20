# SPEC.md – AgentOps-TFT 垂直领域 Agent 全链路落地框架 规格文档
> 版本：v0.1 日期：2025‑07‑15 作者：DwainYu 状态：草案（供开发/评审/面试对齐）

---  

## 1. 项目愿景 & 范围  

| 项 | 说明 |
|----|------|
| **愿景** | 在《云顶之弈》（TFT）垂直域构建 **可复用、可观测、可评测、可扩展** 的 Agent 应用全链路标杆，覆盖 *数据采集 → 清洗 → Embedding → 向量/图检索 → 多 Agent 编排 → 工具调用 → 推理加速 → 评测飞轮 → 观测闭环*。 |
| **核心交付** | 1️⃣ 可在本地/云端一键启动的 **FastAPI + LangGraph + vLLM** 服务  <br>2️⃣ **自动化评测流水线**（Ragas/DeepEval + CI）  <br>3️⃣ **数据飞轮最小闭环**（爬虫 → 入库 → 微调 → 线上灰度 → 反馈 → 再训练）  <br>4️⃣ **全链路观测告警**（LangSmith/MLflow + Prometheus/Grafana）  <br>5️⃣ **开源级文档/博客/视频**（README、架构图、指标看板、复盘文章） |
| **非目标** | • 通用聊天机器人、多模态对话、大规模分布式训练、商业化 SaaS 运营 |

---  

## 2. 用户故事（User Stories）  

| ID | 角色 | 故事 | 优先级 | 验收标准（AC） |
|----|------|------|--------|----------------|
| **US‑01** | **玩家/分析师** | 作为 TFT 玩家，我想在 Web UI 输入“当前版本最强阵容”，获得 **流式、可解释、可人工干预** 的推荐答案。 | P0 | 1. SSE/WS 实时返回 Token 流  <br>2. 答案包含阵容、装备、运营节奏、关键决策点 <br>3. 支持“人工介入”按钮：暂停/修正/继续 |
| **US‑02** | **算法工程师** | 我需要 **一键跑通** “爬虫 → 清洗 → Embedding → 向量/图入库 → 评测” 最小飞轮，且指标可在 CI 中自动回归。 | P0 | 1. `make data-flywheel` 单命令完成全流程 <br>2. CI 汇总耗时 ≤ 30 min <br>3. Recall@10 ≥ 90%、P99 ≤ 400 ms |
| **US‑03** | **平台运维** | 我要在 **Prometheus/Grafana** 看到业务指标（推荐准确率、工具成功率、队列积压）与系统指标（QPS、P99、GPU 利用率），并配置告警。 | P0 | 1. 仪表盘含 ≥ 10 个核心面板 <br>2. 告警规则覆盖 SLO（可用性 99.9%、P99 < 500 ms、GPU 利用率 > 60%） |
| **US‑04** | **开源贡献者** | 我希望阅读 **架构图、接口契约、贡献指南**，能在 10 分钟内提交首个 PR（文档/测试/小重构）。 | P1 | 1. `CONTRIBUTING.md`、`ARCHITECTURE.md`、`API_CONTRACT.md` 完整 <br>2. 首个 PR 合入 ≤ 1 次 Review |
| **US‑05** | **面试官/评审者** | 我需要在 5 分钟内理解 **核心难点、技术选型理由、关键指标、可复用模块**，以便深挖。 | P1 | 1. `SPEC.md`、`README.md`、`DESIGN_DECISIONS.md` 覆盖上述维度 <br>2. 关键指标均有压测报告链接 |

---  

## 3. 功能需求 & 验收标准（Functional Requirements & Acceptance Criteria）  

| 模块 | 功能点 | 详细验收标准（Given/When/Then） | 关键指标 |
|------|--------|--------------------------------|----------|
| **F‑01 网关层** | FastAPI Gateway（Auth、限流、熔断、请求追踪、SSE/WS） | - Given 合法 JWT，When 并发 200 QPS，Then 成功率 100%、P99 < 50 ms <br>- Given 超限流阈值，Then 返回 429 + Retry‑After | QPS 200、P99 < 50 ms、错误率 < 0.01% |
| **F‑02 Agent 编排** | LangGraph StateGraph：Planner → Executor(RAG/Tool) → Critic → Reflect → Memory；Checkpoint 恢复；Human‑in‑loop 中断/修正 | - Given 多轮对话，When 用户点击“暂停”，Then 状态持久化至 PostgreSQL，再次请求可从断点继续 <br>- Given 工具并发调用 5 个，Then 总耗时 ≤ 单工具耗时 × 1.2 | 单轮决策 P99 < 800 ms、Checkpoint 恢复 < 200 ms |
| **F‑03 RAG Engine** | Hybrid Search（Dense BGE‑M3 + Sparse BM25） → BGE‑Reranker → GraphRAG 两跳推理 | - Given 10k 文档语料，When 查询 “S13 版本最强刺客阵容”，Then Recall@10 ≥ 92%、MRR ≥ 0.78 <br>- Given GraphRAG 开启，Then 全局检索准确率较纯向量提升 ≥ 15% | Recall@10 92%+、P99 380 ms |
| **F‑04 Tool Registry** | 15+ Function Calling 工具（Riot API、DataDragon、Calculator、Python REPL、Web Search、Vector Search、Graph Query、Cache、RateLimiter、Logger、Tracer 等） | - Given Agent 决策调用 3 个工具并发，Then 所有工具在 500 ms 内返回、错误自动重试 2 次、熔断后降级返回默认值 <br>- Schema 版本化（v1/v2）兼容 | 工具成功率 99.2%、并发加速比 ≥ 1.8 |
| **F‑05 推理服务** | vLLM / SGLang 部署 Qwen2.5‑14B‑AWQ‑4bit；开启 PagedAttention、Chunked Prefill、Prefix Cache | - Given 并发 64，When 压测 10 min，Then 吞吐 ≥ 1800 tok/s、P99 ≤ 250 ms、显存 ≤ 18 GB <br>- 对比 FP16 基线，准确率下降 ≤ 1% (BLEU/ROUGE) | 吞吐 1800 tok/s、显存 -40%、成本 -60% |
| **F‑06 数据飞轮** | 爬虫（Playwright/httpx+asyncio）→ 清洗 → Embedding (BGE‑M3) → Milvus + Neo4j → 线上灰度（10%）→ 隐式反馈（点击/停留） → LoRA 微调 → 再入库 | - 日增量 50k+ 对局，去重率 ≥ 99% <br>- 灰度 1 周后 Recall@10 提升 ≥ 3% <br>- 微调周期 ≤ 24 h | 数据新鲜度 ≤ 2 h、飞轮周转 ≤ 48 h |
| **F‑07 评测体系** | Ragas/DeepEval 200+ 测试集（检索、生成、工具调用、多轮一致性）；CI 集成；Prompt 版本管理；A/B 测试框架 | - `pytest -m eval` 全通过 <br>- Prompt vN 与 vN‑1 显著性检验 p < 0.05 <br>- A/B 流量分桶 10%/90% 可配置 | 回归捕获率 100%、评测耗时 ≤ 15 min |
| **F‑08 观测告警** | LangSmith/MLflow Trace → Prometheus Exporters → Grafana Dashboard → AlertManager（钉钉/企业微信） | - 任一请求可在 LangSmith 看到完整 Trace（Gateway → Agent → Tool → LLM） <br>- 核心 SLO 告警触发 ≤ 1 min、无告警风暴 | 可观测覆盖 100%、MTTD < 2 min |
| **F‑09 工程化交付** | Docker 多阶段构建（base→builder→runtime）、GitHub Actions（lint、test、build、push、deploy‑kind）、Kind 集成测试、Blue‑Green 部署、GPU HPA | - `make docker-push` 单命令推镜像 <br>- CI 通过率 100% <br>- Kind 集群滚动升级零停机 | 镜像 < 1.2 GB、部署 < 5 min |

---  

## 4. 非功能需求（NFR）  

| 类别 | 指标 | 目标 |
|------|------|------|
| **性能** | 网关 QPS | ≥ 200 |
| | Agent 单轮 P99 | ≤ 800 ms |
| | RAG 检索 P99 | ≤ 400 ms |
| | LLM 推理吞吐 | ≥ 1800 tok/s (64 并发) |
| **可用性** | 服务 SLA | 99.9%（月停机 ≤ 43 min） |
| | 数据飞轮端到端延迟 | ≤ 2 h |
| **可扩展** | 水平扩容 | Gateway/Executor/Tool 横向无状态，GPU 池 HPA |
| | 多模型热插拔 | vLLM/SGLang/Triton 统一 `/v1/completions` 接口 |
| **安全** | 认证 | JWT + RBAC（admin/operator/viewer） |
| | 数据 | 传输 TLS 1.3、存储加密（AES‑256） |
| **合规** | 日志审计 | 所有请求/工具调用/模型推理含 request_id、user_id、trace_id |
| **文档** | 代码注释覆盖 | ≥ 80%（public API） |
| | 架构/接口/决策文档 | 100% 覆盖核心模块 |

---  

## 5. 技术选型理由（Design Decisions）  

| 决策点 | 备选 | 选择 | 理由（关键词） |
|--------|------|------|----------------|
| **Agent 编排框架** | AutoGen, CrewAI, LangChain `AgentExecutor`, **LangGraph** | **LangGraph** | 状态机显式建模、Checkpoint 原生、Human‑in‑loop 友好、可视化 Graph、社区活跃、易于单测 |
| **Web 框架** | Flask, Starlette, **FastAPI** | **FastAPI** | 原生 async、依赖注入、OpenAPI 自动生成、SSE/WS 内置、生产级中间件生态 |
| **向量数据库** | Pinecone, Weaviate, Qdrant, **Milvus/Zilliz** | **Milvus** | 纯本地部署、Hybrid Search 原生、分区/索引灵活、K8s Operator 成熟、社区中文文档完善 |
| **图数据库** | Neo4j, JanusGraph, **Kuzu** | **Neo4j** | Cypher 标准、全文索引、APOC 过程、生产级备份/集群、Python 驱动成熟 |
| **Embedding** | OpenAI text‑embedding‑3‑large, **BGE‑M3**, Jina‑v2 | **BGE‑M3** | 中文/代码/多语言 SOTA、支持稠密+稀疏+多向量、可 LoRA 微调、Apache‑2.0 可商用 |
| **Reranker** | Cohere Rerank, **BGE‑Reranker**, MonoT5 | **BGE‑Reranker** | 同源 Embedding、零样本泛化强、推理快（ONNX/INT8） |
| **LLM 推理引擎** | TGI, **vLLM**, SGLang, TensorRT‑LLM | **vLLM** (主) + **SGLang** (对比) | PagedAttention 显存友好、Chunked Prefill/Prefix Cache 低延迟、开源活跃、易 K8s 部署 |
| **量化** | GPTQ, AWQ, **GGUF**, FP8 | **AWQ‑4bit** | 推理速度/显存/精度平衡最好、vLLM 原生支持、无需重训练 |
| **爬虫** | Scrapy, **Playwright**, httpx+asyncio | **httpx+asyncio** (主) + **Playwright** (动态页) | 轻量、全异步、易控并发/重试/限流、无浏览器依赖 |
| **任务调度/流水线** | Airflow, Prefect, **Dagster**, GitHub Actions | **GitHub Actions + Dagster (可选)** | 代码即流水线、零运维、CI 原生、Dagster 供后期数据资产管理 |
| **评测** | Ragas, DeepEval, **LangSmith Eval**, TruLens | **Ragas + DeepEval + LangSmith** | Ragas 专注 RAG、DeepEval 通用、LangSmith 可视化 Trace、三者互补 |
| **监控** | Datadog, **Prometheus+Grafana**, VictoriaMetrics | **Prometheus+Grafana** | 全开源、K8s 原生、告警规则灵活、成本可控 |
| **链路追踪** | Jaeger, Zipkin, **LangSmith**, OpenTelemetry | **LangSmith + OTel** | LangSmith 专为 LLM/Tool 设计、OTel 统一导出 Prometheus |
| **容器编排** | Docker Swarm, Nomad, **Kubernetes (Kind/Minikube → EKS/GKE)** | **K8s** | 生产标准、GPU 调度、HPA、滚动发布、生态完善 |
| **前端** | React+Vite, **Next.js 14**, SvelteKit | **Next.js 14 (App Router)** | SSR/ISR、Server Actions、流式响应原生、Vercel 免费部署 |
| **CI/CD** | GitLab CI, CircleCI, **GitHub Actions** | **GitHub Actions** | 代码托管同平台、免费额度大、Matrix/Env/Secrets 完善 |
| **秘钥管理** | Vault, SealedSecrets, **GitHub Environments + SOPS** | **GitHub Environments + SOPS** | 免运维、审计友好、配合 K8s SealedSecrets |

> **决策记录**：每项决策在 `DESIGN_DECISIONS.md` 中保留 **背景、备选、评分矩阵、最终选择、回滚条件**。

---  

## 6. 接口契约（API Contracts）  

### 6.1 网关层 – 对外 REST / SSE  

| Method | Path | 描述 | 请求体 | 响应 | 认证 | 限流 |
|--------|------|------|--------|------|------|------|
| `POST` | `/v1/chat/completions` | 统一聊天入口（兼容 OpenAI Chat Completion） | `{model, messages[], stream?, tools?, tool_choice?, temperature?, max_tokens?}` | 流式 `data: {choices:[{delta:{content|tool_calls}}]}` / 非流式 JSON | Bearer JWT (scope `chat`) | 200 req/min per user |
| `GET` | `/v1/health` | 健康检查 | — | `{status:"ok", version, git_sha, uptime}` | 无 | 1000 req/min |
| `GET` | `/v1/metrics` | Prometheus 拉取 | — | `text/plain` metrics | 内网 IP 白名单 | — |

#### 6.1.1 `ChatCompletionRequest` Schema (JSON Schema)  

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ChatCompletionRequest",
  "type": "object",
  "required": ["model","messages"],
  "properties": {
    "model": {"type":"string","enum":["qwen2.5-14b-awq","qwen2.5-7b-awq"]},
    "messages": {
      "type":"array",
      "items":{"$ref":"#/definitions/Message"},
      "minItems":1
    },
    "stream": {"type":"boolean","default":true},
    "tools": {"type":"array","items":{"$ref":"#/definitions/ToolSpec"}},
    "tool_choice": {"type":["string","object"],"enum":["auto","none"]},
    "temperature": {"type":"number","minimum":0,"maximum":2,"default":0.7},
    "max_tokens": {"type":"integer","minimum":1,"maximum":8192}
  },
  "definitions": {
    "Message": {
      "type":"object",
      "required":["role","content"],
      "properties":{
        "role":{"type":"string","enum":["system","user","assistant","tool"]},
        "content":{"type":["string","null"]},
        "tool_calls":{"type":"array","items":{"$ref":"#/definitions/ToolCall"}},
        "tool_call_id":{"type":"string"}
      }
    },
    "ToolSpec": {
      "type":"object",
      "required":["type","function"],
      "properties":{
        "type":{"const":"function"},
        "function":{
          "type":"object",
          "required":["name","description","parameters"],
          "properties":{
            "name":{"type":"string"},
            "description":{"type":"string"},
            "parameters":{"type":"object","description":"JSON Schema"}
          }
        }
      }
    },
    "ToolCall": {
      "type":"object",
      "required":["id","type","function"],
      "properties":{
        "id":{"type":"string"},
        "type":{"const":"function"},
        "function":{"type":"object","required":["name","arguments"],"properties":{"name":{"type":"string"},"arguments":{"type":"string"}}}
      }
    }
  }
}
```

#### 6.1.2 流式响应示例  

```
data: {"id":"cmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"当前版本最强阵容为 "},"finish_reason":null}]}
data: {"id":"cmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"query_riot_api","arguments":"{\"endpoint\":\"/tft/meta\"}"}}]},"finish_reason":null}]}
...
data: {"id":"cmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

---  

### 6.2 内部 gRPC / HTTP（Agent ↔ Tool / RAG / Inference）  

| 服务 | 接口 | Proto / OpenAPI 关键字段 |
|------|------|--------------------------|
| **Tool Dispatcher** | `POST /internal/tools/dispatch` | `{tool_name:string, args:json, timeout_ms:int, retry:int}` → `{success:bool, data:json, error?:string}` |
| **RAG Engine** | `POST /internal/rag/query` | `{query:string, top_k:int, hybrid:bool, rerank:bool}` → `{documents:[{id,score,content,metadata}], latency_ms:int}` |
| **Inference** | `POST /v1/completions` (兼容 OpenAI) | 标准 OpenAI Completion 请求/响应 |
| **Graph Query** | `POST /internal/graph/query` | `{cypher:string, params:json}` → `{records:[json], latency_ms:int}` |
| **Metrics Exporter** | `GET /internal/metrics` | Prometheus 文本格式 |

> 所有内部接口统一 **请求头**：`X-Request-ID`、`X-User-ID`、`X-Trace-ID`，便于全链路追踪。

---  

## 7. 验收测试计划（Acceptance Test Plan）  

| 测试层级 | 工具/脚本 | 覆盖范围 | 通过标准 |
|----------|-----------|----------|----------|
| **单元测试** | `pytest -m unit` | 各 Service/Router/Tool 纯逻辑 | 行覆盖 ≥ 85%、无 Flaky |
| **集成测试** | `pytest -m integration` (Kind 集群) | Gateway→Agent→Tool→RAG→Inference 全链路 | 核心用例 100% 通过、P99 指标达标 |
| **契约测试** | `schemathesis` + OpenAPI | 对外 REST/SSE 接口契约 | 请求/响应 100% 符合 Schema |
| **性能/压测** | `locust` / `hey` | 网关 QPS、Agent 单轮、RAG 检索、vLLM 吞吐 | 指标满足 NFR 表 |
| **评测回归** | `pytest -m eval` (Ragas/DeepEval) | 200+ 测试集（检索、生成、工具、多轮） | Recall@10 ≥ 90%、BLEU/ROUGE 无显著回归 |
| **混沌/故障注入** | `chaosmesh` (Kind) | Tool 熔断、GPU OOM、网络分区 | 服务自动降级、SLO 未破、告警触发 ≤ 1 min |
| **文档/示例** | `make docs-check` | README、ARCHITECTURE、API_CONTRACT、CONTRIBUTING 完整性 | 无断链、示例可运行 |

---  

## 8. 交付物清单（Deliverables）  

| 交付物 | 位置 | 说明 |
|--------|------|------|
| **源码** | `api/`, `data_collection/`, `eval/`, `infra/` | 模块化、可独立测试 |
| **Dockerfile / docker-compose.yml** | 根目录 | 多阶段构建、GPU 支持、本地一键启动 |
| **GitHub Actions Workflows** | `.github/workflows/` | lint、test、build、push、deploy‑kind、eval |
| **K8s Manifests (Kind/Prod)** | `infra/k8s/` | Deployment、Service、HPA、Secret、ConfigMap |
| **Prometheus/Grafana Dashboards** | `infra/monitoring/` | 业务+系统双维面板、告警规则 |
| **LangSmith/MLflow 项目** | `infra/observability/` | Trace、Experiment、Evaluation 配置 |
| **评测数据集 & 脚本** | `eval/datasets/`, `eval/scripts/` | 200+ 样本、CI 集成 |
| **文档** | `README.md`, `ARCHITECTURE.md`, `API_CONTRACT.md`, `DESIGN_DECISIONS.md`, `CONTRIBUTING.md`, `SPEC.md` | 完整、可渲染、含架构图 |
| **技术博客/视频** | `docs/blog/` | 《从 0 到 92% Recall：垂直域 Agent 数据飞轮实战》 |
| **开源贡献记录** | `CONTRIBUTORS.md` | PR 链接、Issue 链接、贡献类型 |

---  

## 9. 里程碑（Milestones）  

| Week | 交付物 | 可对外展示的产出 |
|------|--------|------------------|
| **W1** | 脚手架 + 核心骨架 | `FastAPI + LangGraph + Docker Compose` 跑通、SSE 流式对话、基础 Tool Registry、GitHub Actions CI |
| **W2** | RAG Engine v1 | Milvus 混合检索、BGE‑Reranker、200 条测试集、Ragas 评测报告、Recall@10 > 80% |
| **W3** | Agent 编排 + 工具生态 | Planner/Executor/Critic/Reflect 状态机、10+ 工具、Human‑in‑loop Demo、LangSmith Trace |
| **W4** | 推理加速 + vLLM 部署 | Qwen2.5‑14B AWQ 4bit、并发压测报告、P99/P999/吞吐对比表、显存/成本分析 |
| **W5** | 数据飞轮 + GraphRAG | 爬虫日增 50k+、Graph 构建管线、Embedding LoRA 微调、A/B 测试框架、线上灰度 10% |
| **W6** | 观测体系 + 文档开源 | Prometheus+Grafana 全景 Dashboard、SLO/告警规则、README/架构图/博客/视频、提交 2-3 个上游 PR |

> **关键原则**：**每周末必须产出可演示/可截图/可写进简历的增量**，不要憋大招。

---  

## 10. 附录  

### 10.1 术语表  
| 缩写 | 全称 |
|------|------|
| RAG | Retrieval‑Augmented Generation |
| SLO | Service Level Objective |
| HPA | Horizontal Pod Autoscaler |
| AWQ | Activation‑aware Weight Quantization |
| LoRA | Low‑Rank Adaptation |
| OTel | OpenTelemetry |

### 10.2 参考链接  
- LangGraph 官方文档：https://langchain-ai.github.io/langgraph/  
- vLLM 设计论文：https://arxiv.org/abs/2309.06180  
- BGE‑M3 技术报告：https://arxiv.org/abs/2402.03216  
- Ragas 评测指南：https://docs.ragas.io/  
- Milvus Hybrid Search：https://milvus.io/docs/hybrid_search.md  

---  

**文档结束** — 请在评审会上对照 **用户故事、验收标准、关键指标、技术选型理由、接口契约** 逐项确认，确认无异议后进入 W1 实施已把完整 **SPEC.md** 写入 `D:/ghq/github.com/DwainYu/tft-agent-set17/SPEC.md`。  

你可以直接在仓库根目录看到该文件，后续：

1. **评审/面试** 时按「用户故事 → 验收标准 → 关键指标 → 技术选型理由 → 接口契约」逐节对齐  
2. **开发冲刺** 按里程碑（W1‑W6）把每个 AC 拆成 Issue/PR  
3. **CI/CD** 已在规格里定好 `pytest -m unit/integration/eval` 与 `make data-flywheel` 等命令，直接落地到 GitHub Actions  

需要把 SPEC 拆成 Issue、生成首周脚手架代码、或把规格里的接口契约生成 OpenAPI/Proto 文件，随时告诉我。