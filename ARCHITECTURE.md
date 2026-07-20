# 系统架构文档 — TFT Agent Set 17

> 最后更新: 2025-07 | 维护者: @DwainYu

---

## 1. 系统概述

TFT Agent Set 17（"云顶虾神"）是一款面向 **Teamfight Tactics (TFT) Set 17 "Space Gods"** 赛季的垂直领域 AI Agent 平台。系统覆盖从数据采集、向量化存储、语义检索、大模型推理到阵容推荐的 **全链路智能决策**，核心目标：

- **实时数据采集** — 通过 Riot API 抓取对局、棋子、装备、_augment_ 等数据
- **向量化检索** — 利用 BGE-M3 将非结构化数据嵌入 Milvus，实现语义搜索
- **知识图谱** — Neo4j 存储棋子协同、装备克制等图关系
- **大模型推理** — vLLM 部署 Qwen2.5-14B-Instruct-AWQ，提供自然语言交互
- **Agent 编排** — LangGraph 构建多步推理、工具调度、记忆管理的 Agent 工作流
- **可观测性** — Prometheus + Grafana + LangSmith 全栈监控

---

## 2. C4 模型

### 2.1 Context Diagram — 系统上下文

```mermaid
C4Context
    title TFT Agent Set 17 — 系统上下文图

    Person(user, "TFT 玩家", "通过 Web UI 提问阵容、装备、数据查询")
    System(tft_agent, "TFT Agent Set 17", "TFT 垂直领域 AI Agent，提供智能问答与推荐")

    System_Ext(riot_api, "Riot Games API", "提供对局数据、棋子数据、排位数据")
    System_Ext(milvus, "Milvus 向量数据库", "存储和检索文本/对局嵌入向量")
    System_Ext(neo4j, "Neo4j 图数据库", "存储棋子协同、装备克制等关系图谱")
    System_Ext(vllm, "vLLM 推理引擎", "部署 Qwen2.5-14B 提供 LLM 推理")
    System_Ext(grafana, "Grafana 监控面板", "可视化系统指标与告警")

    Rel(user, tft_agent, "HTTP/SSE 交互", "浏览器")
    Rel(tft_agent, riot_api, "REST API 调用", "HTTPS")
    Rel(tft_agent, milvus, "向量检索", "gRPC")
    Rel(tft_agent, neo4j, "图查询", "Bolt")
    Rel(tft_agent, vllm, "推理请求", "HTTP")
    Rel(tft_agent, grafana, "指标上报", "HTTP/Prometheus")
```

### 2.2 Container Diagram — 容器视图

```mermaid
C4Container
    title TFT Agent Set 17 — 容器图

    Person(user, "TFT 玩家")

    Container_Boundary(agent_system, "TFT Agent Set 17") {
        Container(frontend, "React Frontend", "Vite + React + TypeScript", "用户交互界面")
        Container(api_gateway, "API Gateway", "FastAPI + Uvicorn", "路由、认证、限流、SSE 端点")
        Container(agent_core, "Agent Core", "LangGraph", "多步推理、意图路由、记忆管理")
        Container(tool_registry, "Tool Registry", "Python", "工具注册表：CompQuery, ItemQuery, AugmentQuery 等")
        Container(rag_engine, "RAG Engine", "LangChain + Milvus + BGE-M3", "检索增强生成，上下文召回")
        Container(inference_engine, "Inference Engine", "vLLM", "大模型推理服务")
        Container(data_pipeline, "Data Pipeline", "Python + aiohttp + Pandas", "Riot API 数据采集与清洗")
        ContainerDb(sqlite, "SQLite / Postgres", "关系型存储", "用户、会话、对局记录")
        ContainerDb(milvus_db, "Milvus", "向量存储", "对局嵌入、阵容嵌入")
        ContainerDb(neo4j_db, "Neo4j", "图存储", "棋子-装备- augment 关系")
    }

    Rel(user, frontend, "浏览器访问", "HTTPS")
    Rel(frontend, api_gateway, "REST + SSE", "HTTP")
    Rel(api_gateway, agent_core, "调度请求", "内部调用")
    Rel(agent_core, tool_registry, "工具调度", "LangGraph ToolNode")
    Rel(agent_core, rag_engine, "上下文检索", "LangChain")
    Rel(agent_core, inference_engine, "推理请求", "HTTP")
    Rel(rag_engine, milvus_db, "向量检索", "gRPC")
    Rel(tool_registry, sqlite, "SQL 查询", "asyncpg/aiosqlite")
    Rel(tool_registry, neo4j_db, "图查询", "Bolt")
    Rel(data_pipeline, sqlite, "数据写入", "batch insert")
    Rel(data_pipeline, milvus_db, "嵌入写入", "gRPC")
    Rel(data_pipeline, neo4j_db, "关系写入", "Bolt")
```

### 2.3 Component Diagram — 组件视图

```mermaid
C4Component
    title TFT Agent Set 17 — Agent Core 组件图

    Container_Boundary(agent_core, "Agent Core (LangGraph)") {
        Component(intent_router, "Intent Router", "LangGraph Node", "识别用户意图：查询、推荐、闲聊")
        Component(entity_matcher, "Entity Matcher", "LangGraph Node", "抽取实体：棋子名、装备名、augment 名")
        Component(tool_dispatcher, "Tool Dispatcher", "LangGraph ToolNode", "根据意图路由到对应工具")
        Component(memory_manager, "Memory Manager", "LangGraph Checkpointer", "管理对话历史与短期记忆")
        Component(response_composer, "Response Composer", "LangGraph Node", "组装最终回复并流式输出")
    }

    Component(comp_query, "CompQuery Tool", "Tool", "查询阵容数据")
    Component(item_query, "ItemQuery Tool", "Tool", "查询装备数据")
    Component(augment_query, "AugmentQuery Tool", "Tool", "查询 augment 数据")
    Component(rag_retriever, "RAG Retriever", "Tool", "语义检索历史对局")

    Component(sse_stream, "SSE Stream", "FastAPI", "Server-Sent Events 推送")

    Rel(intent_router, entity_matcher, "提取实体")
    Rel(entity_matcher, tool_dispatcher, "分发工具")
    Rel(tool_dispatcher, comp_query, "阵容查询")
    Rel(tool_dispatcher, item_query, "装备查询")
    Rel(tool_dispatcher, augment_query, "augment 查询")
    Rel(tool_dispatcher, rag_retriever, "语义检索")
    Rel(memory_manager, intent_router, "上下文注入")
    Rel(comp_query, response_composer, "结果")
    Rel(item_query, response_composer, "结果")
    Rel(augment_query, response_composer, "结果")
    Rel(rag_retriever, response_composer, "结果")
    Rel(response_composer, sse_stream, "流式推送")
```

---

## 3. 数据流序列图

```mermaid
sequenceDiagram
    actor User as 用户 (浏览器)
    participant FE as React Frontend
    participant API as API Gateway (FastAPI)
    participant IR as Intent Router
    participant EM as Entity Matcher
    participant TD as Tool Dispatcher
    participant TQ as 查询工具 (Comp/Item/Augment)
    participant RAG as RAG Engine (Milvus)
    participant GDB as Neo4j
    participant LLM as vLLM (Qwen2.5)
    participant SSE as SSE Stream

    User->>FE: 输入自然语言问题
    FE->>API: POST /api/chat {message}
    API->>IR: 传入用户消息 + 历史记忆

    IR->>IR: 意图分类 (查询/推荐/闲聊)
    IR->>EM: 传递意图 + 原始文本
    EM->>EM: NER 抽取棋子/装备/augment 实体
    EM->>TD: 传递实体 + 意图

    TD->>TQ: 调用对应查询工具
    TQ->>GDB: Cypher 图查询 (协同关系)
    GDB-->>TQ: 图结果
    TQ->>RAG: 语义检索相似对局
    RAG-->>TQ: Top-K 对局上下文

    TQ-->>TD: 汇总查询结果
    TD-->>LLM: 组装 Prompt + 上下文 → 推理请求
    LLM-->>TD: 生成回复 (流式 token)

    TD-->>SSE: 逐 token 推送
    SSE-->>FE: SSE event stream
    FE-->>User: 实时显示回复
```

---

## 4. 技术栈

| 层级 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| **前端** | React + TypeScript + Vite | React 18 / Vite 6 | 用户交互界面 |
| **API 网关** | FastAPI + Uvicorn | FastAPI 0.115+ / Uvicorn 0.32+ | REST + SSE 端点 |
| **Agent 框架** | LangGraph | 0.2+ | 有状态多步推理编排 |
| **工具注册** | LangGraph ToolNode | — | 工具调度与执行 |
| **向量数据库** | Milvus | 2.4+ | 嵌入向量存储与检索 |
| **图数据库** | Neo4j | 5.x | 棋子/装备/augment 关系图谱 |
| **LLM 推理** | vLLM | 0.6+ | 高吞吐 LLM serving |
| **基座模型** | Qwen2.5-14B-Instruct-AWQ | — | 中文优化的指令微调模型 |
| **嵌入模型** | BGE-M3 (BAAI) | — | 多语言、多粒度嵌入 |
| **关系数据库** | SQLite (dev) → Postgres (prod) | SQLite 3 / PG 16 | 用户、会话、对局存储 |
| **数据采集** | aiohttp + Pandas | aiohttp 3.14 / Pandas 3.0 | Riot API 爬虫 |
| **认证** | python-jose + passlib | — | JWT + bcrypt 认证 |
| **包管理** | uv | 0.5+ | 快速依赖管理 |
| **代码质量** | Ruff + Black + mypy | — | lint / format / type-check |
| **CI/CD** | GitHub Actions | — | 自动化测试与部署 |
| **监控** | Prometheus + Grafana | Prom 2.x / Grafana 11 | 指标采集与可视化 |
| **追踪** | LangSmith | — | LLM 调用链追踪 |
| **容器化** | Docker + Docker Compose | — | 开发环境编排 |
| **K8s** | Kind (staging) / EKS/GKE (prod) | — | 生产环境编排 |

---

## 5. 部署架构

### 5.1 开发环境 — Docker Compose

```
┌─────────────────────────────────────────────────┐
│              Docker Compose (dev)                 │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Frontend │  │ API      │  │ Data Pipeline │  │
│  │ (Vite)   │  │ (FastAPI)│  │ (Collector)   │  │
│  │ :5173    │  │ :8000    │  │ cron/manual   │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ SQLite   │  │ Milvus   │  │ Neo4j         │  │
│  │ (volume) │  │ :19530   │  │ :7474/:7687   │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ vLLM     │  │Prometheus│  │ Grafana       │  │
│  │ :8001    │  │ :9090    │  │ :3001         │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────┘
```

### 5.2 Staging — Kind (Kubernetes in Docker)

- 使用 Kind 创建本地 K8s 集群
- Helm Charts 部署各服务
- 镜像推送到 GHCR (`ghcr.io/dwainyu/tft-agent-set17`)
- ArgoCD 或 Flux 实现 GitOps 自动部署

### 5.3 Production — EKS / GKE

- **计算**: GPU 节点池 (A10G/L4) 用于 vLLM；CPU 节点池用于 API 和数据库
- **存储**: EBS/GCE PD 用于 Postgres；S3/GCS 用于 Milvus 对象存储
- **网络**: ALB/GCLB → API Gateway → 内部服务
- **自动扩缩**: HPA 根据 CPU/QPS 扩 API；KEDA 根据队列深度扩 Pipeline
- **安全**: Cert-Manager TLS，Sealed Secrets，RBAC，Network Policies
- **灾备**: Postgres 多 AZ 主从；Milvus 多副本；跨区备份

---

## 6. 安全考量

- JWT 认证 + bcrypt 密码哈希
- Riot API Key 通过 Secrets Manager 管理，不提交到代码仓库
- 所有外部通信走 HTTPS
- RBAC 控制 Agent 工具权限
- LangSmith trace 脱敏处理用户 PII

---

## 7. 演进路线

| 阶段 | 里程碑 | 核心交付 |
|------|--------|---------|
| Phase 1 (当前) | 基础骨架 + CI | FastAPI + React + SQLite + 工具注册表 |
| Phase 2 | Agent 核心 | LangGraph 编排 + LangSmith 追踪 |
| Phase 3 | 数据增强 | Milvus + Neo4j + BGE-M3 嵌入管线 |
| Phase 4 | 推理部署 | vLLM + AWQ 量化 + GPU 调度 |
| Phase 5 | 生产就绪 | K8s + 监控 + 告警 + 灰度发布 |
