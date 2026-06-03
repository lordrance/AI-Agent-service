# Enterprise AI Agent API

**企业级 AI Agent 纯后端服务** —— 无前端 UI，通过 HTTP/JSON（及 SSE 流式）对外提供对话、RAG、文档入库与 ReAct Agent 能力。适合业务系统、移动 App 或运维脚本集成。

[![CI](https://github.com/lordrance/AI-Agent-service/actions/workflows/ci.yml/badge.svg)](https://github.com/lordrance/AI-Agent-service/actions/workflows/ci.yml)

---

## 能做什么

| 能力 | 端点 | 说明 |
|------|------|------|
| 多轮对话 | `POST /api/v1/chat` | LangGraph + Postgres 检查点，会话可恢复 |
| 流式对话 | `POST /api/v1/chat/stream` | SSE，护栏与检查点与非流式一致 |
| 文档入库 | `POST /api/v1/documents/upload` | PDF/TXT → 分块 → 向量 + 元数据 |
| 文档管理 | `GET/DELETE /api/v1/documents` | 租户隔离列表与删除（含向量） |
| RAG 问答 | `POST /api/v1/rag/query` | 向量 + BM25 + RRF 混合检索，可选 LLM 生成 |
| Agent | `POST /api/v1/agent` | ReAct + 工具；`use_memory=true` 启用记忆 |
| 运维 | `/api/v1/health`、`/metrics` | 就绪探针、Prometheus |

---

## 技术栈

| 类别 | 选型 |
|------|------|
| Web | FastAPI、Gunicorn、Uvicorn |
| Agent | LangGraph、LangChain |
| 向量库（生产） | **Pinecone**（namespace = 租户 ID） |
| 向量库（本地/CI） | **pgvector**（PostgreSQL 扩展） |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis |
| 鉴权 | API Key + JWT、slowapi 限流 |
| 可观测 | Prometheus、Langfuse（可选）、OpenTelemetry（可选 OTLP） |

> Milvus 已从主链路移除，代码仅保留并标记 **deprecated**。

---

## 快速开始

### 1. 环境要求

- Python **3.11+**
- PostgreSQL 16（含 pgvector）与 Redis（本地或 Docker）

### 2. 安装与配置

```bash
cd project-python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env：至少配置 DATABASE_URL、REDIS_URL
# 使用对话/RAG 生成时需 OPENAI_API_KEY
```

### 3. 数据库迁移

```bash
alembic upgrade head
```

### 4. 启动（开发）

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 健康检查：<http://127.0.0.1:8000/api/v1/health>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

### 5. Docker Compose（推荐联调）

```bash
docker compose up -d --build
./scripts/smoke_deploy.sh http://127.0.0.1:8000
```

Compose 包含 **app + Postgres(pgvector) + Redis**。向量库默认 `VECTOR_STORE=pgvector`。

---

## 生产：Pinecone

```env
VECTOR_STORE=pinecone
PINECONE_API_KEY=你的密钥
PINECONE_INDEX=agent-knowledge
PINECONE_HOST=控制台中的 Serverless host
EMBEDDING_DIM=1536
```

在 Pinecone 控制台创建 index，**维度须与 `EMBEDDING_DIM` 一致**。每个租户使用独立 **namespace**（与 `tenant_id` 对齐）。

详见 [docs/deployment.md](./docs/deployment.md)。

---

## 鉴权示例

```bash
# 未启用鉴权（默认开发）
curl -s http://127.0.0.1:8000/api/v1/health

# 启用 AUTH_ENABLED=true 后
export API_KEYS="tenant-a:secret-a"
curl -s -H "X-API-Key: secret-a" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"你好"}]}' \
  http://127.0.0.1:8000/api/v1/chat
```

---

## RAG 黄金集评估

```bash
# 校验数据集格式
python scripts/eval_rag_golden.py --dry-run

# 真实管道（写入 pgvector → 混合检索 → 打分）
python scripts/eval_rag_golden.py --mode pipeline --fail-under 0.8
```

CI 对黄金集要求 **accuracy ≥ 0.8**（见 `.github/workflows/ci.yml`）。

---

## 测试

```bash
alembic upgrade head
pytest tests/ -q
ruff check app tests scripts
```

---

## 目录结构

```
project-python/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/routes/          # chat、document、rag、agent、health
│   ├── core/                # Agent、RAG、记忆、护栏、LangGraph
│   └── infrastructure/      # LLM 路由、Pinecone/pgvector、DB、OTel
├── alembic/                 # 数据库迁移
├── scripts/                 # 评估脚本、冒烟测试
├── tests/                   # pytest（60+ 用例）
├── docker-compose.yml
└── docs/deployment.md
```

---

## 相关文档

- [部署指南](./docs/deployment.md)
- [API 示例](./docs/api-examples.md)
- 规划：`../docs/planning-artifacts/project-prompt.md`

---

## 许可证

MIT
