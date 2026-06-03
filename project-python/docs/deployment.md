# 生产部署指南（Epic 5）

本文说明如何将 **enterprise-ai-agent** 以容器方式部署到生产/预发环境，涵盖镜像构建、Compose、Kubernetes、数据库迁移、扩缩容与回滚。

## 1. 架构概览

```
                    ┌─────────────┐
  Clients ─────────►│  Ingress/LB │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │  Gunicorn + UvicornWorker │  (非 root, /api/v1/health)
              │  FastAPI app              │
              └─┬──────────┬──────────┬─┘
                │          │          │
         ┌──────▼───┐ ┌────▼────┐ ┌───▼──────┐
         │ Postgres │ │  Redis  │ │ OpenAI   │
         │ pgvector │ │         │ │ API      │
         └──────────┘ └─────────┘ └──────────┘
```

主向量库为 **pgvector**（与 Alembic 迁移一致）。Milvus 为历史可选组件，默认 Compose 栈不再包含。

## 2. 生产镜像（S5.1）

### 构建

```bash
cd project-python
docker build -t enterprise-ai-agent:$(git rev-parse --short HEAD) .
```

特性：

- **多阶段构建**：builder 安装依赖，runtime 仅保留 venv + 应用代码
- **非 root**：UID/GID `10001` 运行
- **HEALTHCHECK**：`GET /api/v1/health`
- **入口**：`docker/entrypoint.sh` → `alembic upgrade head`（可关）→ **gunicorn** + `UvicornWorker`

### 关键环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `RUN_MIGRATIONS_ON_STARTUP` | 启动时跑迁移 | `true` |
| `GUNICORN_WORKERS` | Worker 数 | CPU 公式 |
| `GUNICORN_GRACEFUL_TIMEOUT` | SIGTERM 后等待秒数 | `30` |
| `GUNICORN_TIMEOUT` | 单请求 worker 超时 | `120` |

优雅停机：K8s `terminationGracePeriodSeconds` ≥ 45，并配置 `preStop sleep 5`（见 `deploy/kubernetes/deployment.yaml`）。

## 3. Docker Compose（S5.2）

```bash
cp .env.example .env
# 编辑 OPENAI_API_KEY、AUTH_ENABLED 等
docker compose up -d --build
./scripts/smoke_deploy.sh http://127.0.0.1:8000
```

栈内服务：`app`、`postgres`（pgvector/pg16）、`redis`。

## 4. Kubernetes 样例（S5.2）

```bash
kubectl apply -f deploy/kubernetes/configmap.yaml
# 先创建 Secret（勿提交真实 secret.yaml）
kubectl apply -f deploy/kubernetes/secret.example.yaml  # 仅作模板，请替换后 apply
kubectl apply -f deploy/kubernetes/deployment.yaml
kubectl apply -f deploy/kubernetes/service.yaml
```

将镜像 tag 改为你的仓库地址，例如 `registry.example.com/enterprise-ai-agent:v1.0.0`。

### 密钥管理建议

- **OPENAI_API_KEY**、**JWT_SECRET**、**API_KEYS** → K8s Secret 或云厂商 Secret Manager
- 非敏感配置 → ConfigMap
- 本地开发用 `.env`（勿提交 Git）

## 5. PgBouncer 与连接池（S5.2）

应用使用 **SQLAlchemy async** + **asyncpg**；LangGraph 检查点亦走 Postgres。

推荐生产拓扑：

```
App (N replicas × M gunicorn workers) → PgBouncer (transaction mode) → PostgreSQL
```

配置要点：

1. **PgBouncer `pool_mode=transaction`** 与 async SQLAlchemy 兼容性好
2. 限制总连接：`workers × replicas × pool_size < PgBouncer max_client_conn`
3. `DATABASE_URL` 指向 PgBouncer，例如：
   `postgresql+asyncpg://user:pass@pgbouncer:6432/agent_db`
4. Postgres `max_connections` 应大于 PgBouncer 到后端的真实连接数

向量检索使用独立 **asyncpg 池**（`PgVectorStore`），计入总连接预算。

## 6. 数据库迁移

```bash
# 手动（CI/CD 发布步骤推荐）
alembic upgrade head

# 容器内默认自动执行（可关闭）
RUN_MIGRATIONS_ON_STARTUP=false
```

**回滚策略**：

1. 应用回滚到上一镜像 tag（K8s `kubectl rollout undo`）
2. 若新版本 migration 已执行且不可逆，需提前准备 `downgrade` 脚本或向前兼容迁移
3. 发布顺序建议：**先迁移（兼容旧版）→ 再滚应用** 或 **先滚应用 → 再迁移（仅 additive）**

## 7. 扩缩容（S5.3）

| 维度 | 建议 |
|------|------|
| **水平** | K8s HPA 基于 CPU 或自定义 `http_requests_total` |
| **Gunicorn workers** | 每副本 `2×CPU+1` 为起点，IO 密集（LLM）宜偏低 |
| **Postgres** | 垂直扩容或读副本（RAG 只读可考虑） |
| **Redis** | 会话/限流状态；多副本需 Redis 集群或统一 storage_uri |

## 8. 冒烟测试（S5.3）

```bash
chmod +x scripts/smoke_deploy.sh
./scripts/smoke_deploy.sh http://localhost:8000
```

检查项：存活、就绪（DB/Redis/pgvector）、Prometheus metrics、可选 RAG。

## 9. 可观测性对接

- **Prometheus**：抓取 `/api/v1/metrics`
- **Langfuse**：`LANGFUSE_ENABLED=true`
- **OTel**：`OTEL_ENABLED=true` 并配置 Collector exporter（需自行挂载 SDK exporter）

## 10. 故障排查

| 现象 | 可能原因 |
|------|----------|
| 启动失败 migration | DB 未就绪；检查 `depends_on` / 重试 |
| `/health/ready` degraded | Redis 或 pgvector 扩展未安装 |
| 502 超时 | 增大 `GUNICORN_TIMEOUT` / `LLM_TIMEOUT_SECONDS` |
| 连接耗尽 | 降低 worker 或加 PgBouncer |
