# AI-Agent-service

**企业级 AI Agent 纯后端 API**（Python / FastAPI）。无前端页面，供业务系统通过 HTTP 集成：多轮对话、RAG 知识库、文档入库、ReAct Agent、多租户鉴权与生产可观测性。

> 本仓库在 [BMAD 模板](https://github.com/bmad-code-org/BMAD-METHOD) 之上落地了可运行的 **Enterprise AI Agent** 服务，主代码在 [`project-python/`](./project-python/)。

---

## 特性一览

- **LangGraph** 对话图 + Postgres 会话检查点
- **混合 RAG**：Pinecone/pgvector 向量检索 + BM25 + RRF 融合
- **Pinecone** 生产向量库（namespace 租户隔离）；**pgvector** 本地/CI 降级
- **SSE 流式** `/chat/stream`，与非流式共享护栏与持久化
- **ReAct Agent** + 可选 Redis/向量记忆
- **API Key / JWT**、限流、护栏、Prometheus、可选 Langfuse / OTel OTLP
- **Docker / K8s** 部署样例与 CI（pytest + RAG 黄金集门禁 ≥ 0.8）

---

## 快速开始

```bash
cd project-python
cp .env.example .env
# 配置 DATABASE_URL、REDIS_URL；对话/RAG 生成需 OPENAI_API_KEY

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

或使用 Docker：

```bash
cd project-python && docker compose up -d --build
```

完整说明见 **[project-python/README.md](./project-python/README.md)**。

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 存活 |
| GET | `/api/v1/health/ready` | DB / Redis / 向量库就绪 |
| POST | `/api/v1/chat` | 多轮对话 |
| POST | `/api/v1/chat/stream` | SSE 流式对话 |
| POST | `/api/v1/documents/upload` | 文档入库 |
| GET | `/api/v1/documents` | 文档列表（租户） |
| DELETE | `/api/v1/documents/{id}` | 删除文档与向量 |
| POST | `/api/v1/rag/query` | RAG 问答 |
| POST | `/api/v1/agent` | ReAct Agent |
| GET | `/api/v1/metrics` | Prometheus 指标 |

交互式文档：启动后访问 `/docs`。

---

## 仓库结构

```
├── project-python/          # ★ 主应用（FastAPI）
├── docs/planning-artifacts/ # PRD、架构、项目方案
├── .github/workflows/       # CI
└── .claude/                 # BMAD 技能与 Agent 配置
```

---

## 开发与 CI

```bash
cd project-python
pytest tests/ -q
python scripts/eval_rag_golden.py --mode pipeline --fail-under 0.8
```

---

## 许可证

MIT — 见 [LICENSE](./LICENSE)。

BMAD 相关组件见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。
