# 运维手册 — TFT Agent Set 17

> 本文档面向 SRE / DevOps / 值班人员，覆盖部署、扩缩容、回滚、故障排查与告警处理。

---

## 1. 部署流程

### 1.1 开发环境 (Docker Compose)

```bash
# 一键启动所有服务
make up
# 等价于:
docker compose -f infra/docker/docker-compose.yml up -d --build

# 仅启动后端
docker compose up -d api

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f api

# 停止所有服务
make down
```

**健康检查端点**:
- API: `GET http://localhost:8000/health`
- Milvus: `GET http://localhost:19530/v1/vector/collections`
- Neo4j: `GET http://localhost:7474`
- Grafana: `GET http://localhost:3001/api/health`

### 1.2 Staging 环境 (Kind)

```bash
# 创建 Kind 集群
kind create cluster --config infra/k8s/kind-config.yaml

# 构建并推送镜像
docker build -t ghcr.io/dwainyu/tft-agent-set17:staging .
kind load docker-image ghcr.io/dwainyu/tft-agent-set17:staging

# 部署到 Kind
make deploy-kind
# 等价于:
helm upgrade --install tft-agent infra/k8s/helm/ \
  --namespace tft-staging --create-namespace \
  --set image.tag=staging \
  --values infra/k8s/helm/values-staging.yaml

# 检查部署状态
kubectl get pods -n tft-staging
kubectl get svc -n tft-staging
```

### 1.3 生产环境 (EKS/GKE)

```bash
# 通过 GitHub Actions CD 自动部署
# 手动部署（紧急情况）:
make deploy-prod IMAGE_TAG=v1.2.3

# 蓝绿部署
kubectl apply -f infra/k8s/production/api-green.yaml
kubectl patch service tft-api -p '{"spec":{"selector":{"version":"green"}}}'

# 金丝雀发布（Argo Rollouts）
kubectl argo rollouts set-image tft-api \
  api=ghcr.io/dwainyu/tft-agent-set17:v1.2.4 \
  -n tft-production
```

---

## 2. 扩缩容

### 2.1 Docker Compose (开发/Staging)

```bash
# 水平扩展 API 实例
docker compose --scale api=3

# 配合 Nginx 负载均衡（已在 docker-compose 中配置）
# Nginx 自动将请求分发到 3 个 API 实例
```

### 2.2 Kubernetes HPA (生产)

```bash
# 查看当前 HPA 状态
kubectl get hpa -n tft-production

# 手动扩容 API
kubectl scale deployment tft-api --replicas=5 -n tft-production

# HPA 配置参考（已在 helm chart 中定义）:
# - CPU 目标: 70%
# - 最小副本: 2
# - 最大副本: 10
# - 缩容冷却: 300s
# - 扩容冷却: 60s

# GPU 节点池（vLLM）
# 使用 KEDA 根据推理队列深度扩缩
kubectl get scaledobject -n tft-production
```

---

## 3. 回滚

### 3.1 Docker Compose 回滚

```bash
# 1. 停止当前服务
docker compose down

# 2. 切换到目标版本的镜像 tag
# 修改 docker-compose.yml 中 image tag 或使用环境变量:
IMAGE_TAG=v1.2.2 docker compose up -d

# 3. 验证健康检查
curl http://localhost:8000/health
```

### 3.2 Kubernetes 回滚

```bash
# 查看部署历史
kubectl rollout history deployment/tft-api -n tft-production

# 回滚到上一版本
kubectl rollout undo deployment/tft-api -n tft-production

# 回滚到指定版本
kubectl rollout undo deployment/tft-api --to-revision=3 -n tft-production

# Argo Rollouts 回滚
kubectl argo rollouts abort tft-api -n tft-production
kubectl argo rollouts promote tft-api -n tft-production
```

### 3.3 数据库回滚

```bash
# 数据库迁移回退（Alembic）
alembic downgrade -1   # 回退一个版本
alembic downgrade base  # 回退到初始状态（危险！）

# 查看迁移历史
alembic history --verbose
```

---

## 4. 常见故障排查

### 4.1 API 500 Internal Server Error

**症状**: 用户请求返回 500，日志显示 `Internal Server Error`

**排查步骤**:
```bash
# 1. 查看 API 日志
docker compose logs --tail=100 api
# 或 K8s:
kubectl logs -l app=tft-api --tail=100 -n tft-production

# 2. 检查数据库连接
docker compose exec api python -c "
import sqlite3; conn = sqlite3.connect('data/tft.db')
print(conn.execute('SELECT count(*) FROM sqlite_master').fetchall())
"

# 3. 检查依赖服务状态
docker compose ps  # 确认所有服务 healthy

# 4. 检查最近的代码变更
git log --oneline -10

# 5. 查看 Prometheus 错误指标
# Grafana → API Dashboard → Error Rate Panel
```

**常见原因**:
- SQLite 文件锁（多进程写入冲突） → 切换到 WAL 模式或 Postgres
- Pydantic 验证错误（上游数据格式变更） → 检查 Riot API 响应
- 未捕获异常 → 查看 traceback 定位代码行

### 4.2 SSE 超时 / 连接中断

**症状**: 前端收到部分 token 后连接断开，或长时间无响应

**排查步骤**:
```bash
# 1. 检查 event_generator 日志
docker compose logs --tail=200 api | grep "sse\|event_generator"

# 2. 检查 vLLM 推理延迟
curl -s http://localhost:8001/v1/models | jq .
curl -s http://localhost:8001/health

# 3. 检查 Nginx/ALB 超时配置
# Nginx proxy_read_timeout 应 >= 300s
# ALB idle timeout 应 >= 300s

# 4. 检查 Agent Core 是否存在死循环
# 查看 LangGraph 执行步数是否超过 max_iterations
```

**常见原因**:
- vLLM 推理超时 → 增大 `VLLM_TIMEOUT` 或减小 `max_tokens`
- Nginx/ALB 超时 → 调整 `proxy_read_timeout`
- LangGraph 死循环 → 检查 `max_iterations` 配置
- 前端 EventSource 未正确处理重连 → 检查前端 SSE 逻辑

### 4.3 Milvus 连接失败

**症状**: 日志显示 `MilvusException` 或 `connection refused`

**排查步骤**:
```bash
# 1. 检查 Milvus 容器状态
docker compose ps milvus
docker compose logs --tail=50 milvus

# 2. 测试 Milvus 连通性
docker compose exec api python -c "
from pymilvus import connections
connections.connect(host='milvus', port='19530')
print('Connected successfully')
"

# 3. 检查 Milvus 存储卷
docker volume inspect tft-agent-set17_milvus_data

# 4. 重启 Milvus
docker compose restart milvus
```

**常见原因**:
- Milvus 容器 OOM → 增加内存限制或减少 collection 数量
- etcd 数据损坏 → 清理 etcd 卷并重建 collection
- 网络分区 → 检查 Docker network 配置
- Milvus 版本不兼容 → 检查 pymilvus 与 Milvus 版本匹配

### 4.4 GPU OOM (Out of Memory)

**症状**: vLLM 崩溃，日志显示 `CUDA out of memory`

**排查步骤**:
```bash
# 1. 检查 GPU 状态
nvidia-smi

# 2. 检查 vLLM 日志
docker compose logs --tail=100 vllm

# 3. 检查当前显存占用
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
```

**缓解措施**:

| 方法 | 命令/配置 | 效果 |
|------|----------|------|
| 减小 batch size | `--max-num-seqs 64` → `--max-num-seqs 32` | 降低并发显存 |
| 降低 max_tokens | `--max-model-len 4096` → `--max-model-len 2048` | 减少 KV Cache |
| 增加 tensor-parallel | `--tensor-parallel-size 1` → `--tensor-parallel-size 2` | 多卡分摊 |
| 启用量化 | 使用 AWQ 量化模型 | 降低 ~60% 显存 |
| 启用 PagedAttention | vLLM 默认已启用 | 优化 KV Cache |

### 4.5 Neo4j 查询超时

**症状**: 图查询返回超时或 `Neo4jError: Transaction timeout`

**排查步骤**:
```bash
# 1. 检查 Neo4j 状态
docker compose logs --tail=50 neo4j

# 2. 进入 Neo4j Browser 执行诊断
# 浏览器打开 http://localhost:7474
# 执行: CALL db.stats.retrieveAllGraphStatistics()

# 3. 检查慢查询
# Neo4j Browser → Query Logs

# 4. 优化索引
docker compose exec neo4j cypher-shell \
  "CREATE INDEX IF NOT EXISTS FOR (c:Champion) ON (c.name);"
```

### 4.6 数据采集失败

**症状**: Riot API 返回 403/429，数据更新停滞

```bash
# 1. 检查 API Key 有效性
curl -H "X-Riot-Token: $RIOT_API_KEY" \
  "https://asia.api.riotgames.com/tft/league/v1/challenger?queue=RANKED_TFT"

# 2. 检查 Rate Limit 头
# X-App-Rate-Limit, X-Method-Rate-Limit, X-App-Rate-Limit-Count

# 3. 查看 Pipeline 日志
docker compose logs --tail=100 data-pipeline
```

---

## 5. 监控面板

### 5.1 Grafana 面板

| 面板 | URL | 说明 |
|------|-----|------|
| 总览 | `http://localhost:3001/d/tft-overview/tft-agent-overview` | 全局健康状态 |
| API 指标 | `http://localhost:3001/d/tft-api/api-performance` | QPS、延迟、错误率 |
| Agent 指标 | `http://localhost:3001/d/tft-agent/agent-performance` | 意图识别准确率、工具调用分布 |
| 推理指标 | `http://localhost:3001/d/tft-vllm/vllm-inference` | 吞吐量、TTFT、TPS |
| 数据库 | `http://localhost:3001/d/tft-db/database-stats` | 连接池、查询延迟 |
| Milvus | `http://localhost:3001/d/tft-milvus/milvus-stats` | 向量检索延迟、collection 大小 |

### 5.2 Prometheus 端点

| 服务 | 端点 |
|------|------|
| API | `http://localhost:8000/metrics` |
| vLLM | `http://localhost:8001/metrics` |
| Milvus | `http://localhost:9091/metrics` |
| Node Exporter | `http://localhost:9100/metrics` |

---

## 6. 告警处理

### 6.1 告警路由

```
Prometheus AlertManager
    ├── Critical → PagerDuty (值班人员)
    ├── Warning  → DingTalk 群 (研发群)
    └── Info     → Slack/DingTalk (通知频道)
```

### 6.2 告警规则

| 告警名 | 级别 | 条件 | 处理方式 |
|--------|------|------|---------|
| `APIErrorRateHigh` | Critical | 5xx 错误率 > 5% 持续 5min | 检查日志 → 回滚 |
| `APILatencyHigh` | Warning | P99 延迟 > 10s 持续 10min | 检查依赖服务 → 扩容 |
| `vLLMInferenceDown` | Critical | vLLM 健康检查失败 3min | 重启 vLLM → 检查 GPU |
| `MilvusConnectionLost` | Critical | Milvus 连接失败 | 检查容器 → 重启 |
| `DiskUsageHigh` | Warning | 磁盘使用 > 85% | 清理日志/数据 → 扩容 |
| `GPUMemoryHigh` | Warning | GPU 显存 > 90% 持续 5min | 降低 batch size → 扩容 |
| `RiotAPIRateLimit` | Warning | 429 响应 > 10/min | 降低请求频率 → 检查调度逻辑 |
| `DatabaseConnectionPool` | Warning | 连接池耗尽 | 增加连接池 → 检查泄漏 |

### 6.3 AlertManager 配置参考

```yaml
# infra/prometheus/alertmanager.yml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'dingtalk-warning'

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'

  - name: 'dingtalk-warning'
    webhook_configs:
      - url: 'https://oapi.dingtalk.com/robot/send?access_token=<TOKEN>'
```

---

## 7. On-Call 联系人

| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|---------|------|
| Primary On-Call | TBD | TBD | 第一响应人，处理 Critical 告警 |
| Secondary On-Call | TBD | TBD | 备份，Primary 无法响应时接手 |
| Tech Lead | @DwainYu | GitHub | 架构决策、升级审批 |
| SRE | TBD | TBD | 基础设施、部署、监控 |

> **注意**: 请根据实际情况填写联系人信息。建议每两周轮换 Primary/Secondary On-Call。

---

## 8. 定期维护

| 任务 | 频率 | 操作 |
|------|------|------|
| 依赖更新 | 每周 | `uv lock --upgrade && pre-commit autoupdate` |
| 数据库备份 | 每日 | 自动备份 Postgres dump 到 S3 |
| 日志清理 | 每周 | 清理 30 天以上的日志 |
| SSL 证书检查 | 每月 | Cert-Manager 自动续期，检查告警 |
| 安全扫描 | 每次 PR | Trivy + GitHub Dependabot |
| Milvus Collection 优化 | 每月 | 执行 `compact` 和 `flush` |
