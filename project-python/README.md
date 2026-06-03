# AI Agent 服务（Python 学习/面试骨架）

## 项目简介

本项目提供 **面向面试与自学的可运行骨架**：模块划分参考企业级 Agent 平台（Agent 编排、RAG、记忆、工具、ETL、模型路由与熔断、追踪），采用 **FastAPI** 提供 HTTP API。在 `app/core` 中预留 **Agent 编排**（ReAct、规划、反思）、**RAG**（检索、重排、生成）、**记忆系统**（短/长期）、**工具与意图识别** 等扩展点；在 `app/infrastructure` 中对接 **LLM 路由与熔断**、**Milvus**、**Redis**、**PostgreSQL** 与 **链路追踪**；在 `app/etl` 中承载文档解析、分块与入库流水线。



## 架构说明

- **接入层**：`app/main.py` 创建 FastAPI 应用，`app/api/routes/` 按领域拆分路由（对话、文档、健康检查）。
- **领域核心**：`app/core/` 放置与框架无关的业务能力——Agent 图编排、RAG 管道、记忆策略、工具注册与意图识别。
- **基础设施**：`app/infrastructure/` 封装对外部系统的访问（模型网关、向量库、缓存、关系库、可观测性），便于单测与替换实现。
- **数据与 ETL**：`app/models` 定义 API/领域模型；`app/etl` 负责非结构化文档到向量索引的数据流。

部署上可通过 **Dockerfile** 构建应用镜像，**docker-compose** 一键拉起应用与依赖中间件（详见下文 Compose 说明）。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI、Uvicorn |
| Agent / LLM | LangChain、LangGraph、OpenAI 兼容 API |
| 向量库 | Milvus（pymilvus） |
| 缓存 | Redis |
| 关系库 | PostgreSQL、SQLAlchemy |
| 配置与校验 | Pydantic v2、pydantic-settings |
| 文档处理 | unstructured、pypdf、sentence-transformers |
| 日志与韧性 | loguru、tenacity、httpx |

## 快速开始

### 本地开发

1. Python 3.11+，创建虚拟环境并安装依赖：

```bash
cd project-python
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

2. 复制环境变量并编辑（至少填写 `OPENAI_API_KEY` 等）：

```bash
cp .env.example .env
```

3. 初始化数据库表结构（需已启动 Postgres，连接由 `DATABASE_URL` 指定）：

```bash
alembic upgrade head
```

4. 启动 API（需本机或 Compose 中已启动 Postgres / Redis / Milvus 若你要联调全栈）：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. 访问健康检查：<http://127.0.0.1:8000/api/v1/health>

### Docker Compose（生产对齐栈）

在 `project-python` 目录准备 `.env`（可由 `.env.example` 复制），然后：

```bash
docker compose up -d --build
./scripts/smoke_deploy.sh http://127.0.0.1:8000
```

Compose 包含 **app（gunicorn）**、**PostgreSQL 16 + pgvector**、**Redis**。向量检索走 pgvector，与主链路一致。

完整生产部署说明见 **[docs/deployment.md](./docs/deployment.md)**（K8s 样例、PgBouncer、扩缩容与回滚）。


```bash
# RAG 黄金集评估（可先 --dry-run 校验数据）
pip install -r requirements-eval.txt
python scripts/eval_rag_golden.py --dataset scripts/fixtures/golden_rag_sample.jsonl --dry-run

# Langfuse：在 .env 中设置 LANGFUSE_ENABLED=true 与 keys，调用 /chat 后可在 Langfuse UI 查看 trace
```

## 目录结构说明

```
project-python/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置（pydantic-settings）
│   ├── api/routes/             # 路由：chat、document、health
│   ├── core/                   # Agent、RAG、记忆、工具、意图
│   ├── infrastructure/         # LLM、向量库、缓存、DB、追踪
│   ├── etl/                    # 解析、分块、流水线
│   └── models/                 # schemas、enums
├── requirements.txt
├── requirements-eval.txt      # 可选：RAGAS、Langfuse
├── scripts/
│   ├── eval_rag_golden.py
│   └── fixtures/golden_rag_sample.jsonl
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 许可证

MIT（可按团队需要修改）。
