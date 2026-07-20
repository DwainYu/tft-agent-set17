# 贡献指南 — TFT Agent Set 17

> 感谢你的贡献！本文档将帮助你快速上手开发流程。

---

## 1. 开发环境搭建

### 1.1 前置要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| Python | >= 3.11 | 推荐使用 pyenv 管理 |
| uv | >= 0.5 | 包管理器 ([安装](https://docs.astral.sh/uv/getting-started/installation/)) |
| Docker + Docker Compose | Docker 24+, Compose V2 | 运行依赖服务 |
| Node.js | >= 20 | 前端开发 |
| Git | >= 2.40 | 版本控制 |
| Make | — | 便捷命令（Windows 可用 `winget install GnuWin32.Make`） |

### 1.2 克隆与初始化

```bash
# 克隆仓库
git clone https://github.com/DwainYu/tft-agent-set17.git
cd tft-agent-set17

# 安装 Python 依赖
uv sync

# 安装前端依赖
cd frontend && npm install && cd ..

# 复制环境变量
cp .env.example .env
# 编辑 .env 填入你的 Riot API Key 等配置

# 启动所有服务（API + 前端 + 数据库）
make up

# 运行测试
make test

# 查看完整命令列表
make help
```

### 1.3 安装 pre-commit hooks

```bash
uv tool install pre-commit
pre-commit install
pre-commit run --all-files  # 首次运行确保全部通过
```

---

## 2. 分支策略

```
main (protected) ─────────────────────────────────►
  │
  ├── feat/langgraph-agent-core ──────► PR ──► merge
  │
  ├── fix/sse-timeout-on-long-query ──► PR ──► merge
  │
  ├── chore/add-pre-commit-hooks ─────► PR ──► merge
  │
  └── refactor/tool-registry ────────► PR ──► merge
```

| 分支类型 | 命名规范 | 说明 |
|---------|---------|------|
| `main` | `main` | 受保护分支，仅通过 PR 合入 |
| 功能分支 | `feat/<描述>` | 新功能开发 |
| 修复分支 | `fix/<描述>` | Bug 修复 |
| 维护分支 | `chore/<描述>` | 构建、CI、文档等杂项 |
| 重构分支 | `refactor/<描述>` | 代码重构（不改变功能） |
| 发布分支 | `release/vX.Y.Z` | 版本发布准备 |

---

## 3. Commit 规范

采用 **Commitizen / Conventional Commits** 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 列表

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(agent): add LangGraph intent router` |
| `fix` | Bug 修复 | `fix(sse): resolve timeout on long queries` |
| `docs` | 文档变更 | `docs: update ARCHITECTURE.md diagrams` |
| `refactor` | 重构（不增功能、不修 bug） | `refactor(tools): extract base query class` |
| `test` | 测试相关 | `test(agent): add unit tests for entity matcher` |
| `chore` | 构建/工具链/CI | `chore(ci): add GitHub Actions workflow` |
| `perf` | 性能优化 | `perf(milvus): batch insert for embedding pipeline` |
| `style` | 代码风格（不影响逻辑） | `style: apply ruff formatting` |

### Scope 常用值

`agent` / `api` / `frontend` / `tools` / `data` / `infra` / `ci` / `docs`

---

## 4. PR 流程

```
1. Fork 仓库（外部贡献者）或直接创建分支（核心成员）
2. 从 main 创建分支：git checkout -b feat/your-feature
3. 开发并提交（遵循 commit 规范）
4. 推送分支并创建 Pull Request
5. CI 自动运行：lint + test + build
6. 请求 Code Review（至少 1 人 approve）
7. 所有 CI 通过 + Review 通过后，Squash Merge 到 main
```

### PR 模板

- **标题**: `<type>(<scope>): 简短描述`
- **描述**:
  - 这个 PR 做了什么？
  - 为什么需要这个改动？
  - 如何测试？
  - 关联的 Issue 编号

---

## 5. 代码规范

### 5.1 Python

| 工具 | 用途 | 配置 |
|------|------|------|
| **Ruff** | Linting + Import 排序 | `ruff check` — 行宽 120 |
| **Black** | 代码格式化 | `black` — 行宽 120 |
| **mypy** | 类型检查 | `--strict` 模式（允许 `ignore_missing_imports`） |

```bash
# 本地检查
ruff check . --fix
black .
mypy api/ --strict
```

### 5.2 代码风格要点

- 行宽上限 **120** 字符
- 使用 **type hints** 标注所有函数签名
- 异步函数优先（FastAPI 路由、数据库操作）
- 使用 **Pydantic v2** 定义数据模型
- 错误处理使用自定义异常类，不要裸 `except`
- 所有公共函数/类必须有 **docstring**（Google 风格）

### 5.3 前端

- TypeScript strict 模式
- ESLint + Prettier
- 组件使用函数式组件 + Hooks
- 样式使用 CSS Modules 或 Tailwind CSS

---

## 6. 测试规范

### 测试分层

| 层级 | 标记 | 运行条件 | 说明 |
|------|------|---------|------|
| Unit | `@pytest.mark.unit` | 本地随时跑 | 无外部依赖，快速 |
| Integration | `@pytest.mark.integration` | 需要 Docker 服务 | 数据库、Milvus、Neo4j |
| Eval | `@pytest.mark.eval` | 需要模型端点 | LLM 质量评估 |
| Contract | `@pytest.mark.contract` | schemathesis | API 契约测试 |
| Chaos | `@pytest.mark.chaos` | 需要 K8s | 故障注入 |

```bash
# 运行所有测试
make test

# 仅运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 带覆盖率报告
pytest --cov=api --cov-report=term-missing
```

---

## 7. Issue 模板说明

项目提供以下 Issue 模板：

| 模板 | 用途 |
|------|------|
| **Bug Report** | 报告 Bug — 包含复现步骤、期望行为、实际行为 |
| **Feature Request** | 功能建议 — 描述需求场景、期望方案 |
| **Task** | 开发任务 — 内部跟踪使用 |

创建 Issue 时请选择对应模板，并填写所有必填字段。

---

## 8. 目录结构说明

```
tft-agent-set17/
├── api/                    # FastAPI 后端
│   ├── main.py            # 应用入口
│   ├── routers/           # API 路由
│   ├── models/            # Pydantic 数据模型
│   ├── services/          # 业务逻辑层
│   ├── core/              # 配置、安全、依赖注入
│   └── db/                # 数据库连接与会话管理
├── frontend/              # React + Vite 前端
│   ├── src/
│   │   ├── components/    # UI 组件
│   │   ├── pages/         # 页面
│   │   ├── services/      # API 调用层
│   │   └── App.tsx        # 应用入口
│   └── package.json
├── data_collection/       # Riot API 数据采集脚本
├── data/                  # 本地数据文件（SQLite 等）
├── tests/                 # 测试目录
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── infra/                 # 基础设施配置
│   ├── docker/            # Dockerfile 和 docker-compose
│   └── k8s/               # Kubernetes manifests
├── docs/                  # 文档
├── proto/                 # Protobuf 定义（如有）
├── ARCHITECTURE.md        # 系统架构文档
├── DESIGN_DECISIONS.md    # 设计决策记录
├── RUNBOOK.md             # 运维手册
├── CONTRIBUTING.md        # 贡献指南（本文档）
├── pyproject.toml         # Python 项目配置
├── Dockerfile             # 容器构建
├── SPEC.md                # 产品规格说明
└── Makefile               # 便捷命令
```

---

## 9. 沟通渠道

- **GitHub Discussions** — 功能讨论与 Q&A
- **GitHub Issues** — Bug 报告与任务跟踪
- **DingTalk/WeChat 群** — 日常沟通（联系项目维护者加入）
