# 架构设计 — 企业级 AI Agent 服务（生产化）

- 版本: 0.1
- 状态: Draft
- 关联: `docs/planning-artifacts/prd.md`

## 1. 总览

无状态 FastAPI 接入层 + 领域核心（LangGraph 编排 / RAG / 记忆 / 工具 / 护栏）+ 基础设施（LLM 路由、向量库、缓存、关系库、追踪）。状态通过 Postgres（业务表 + LangGraph 检查点）与 Redis（短期记忆/限流）外置，支持水平扩展。

```
HTTP 层 (FastAPI · 无状态)
  middleware: 请求ID → 结构化日志 → 鉴权 → 限流 → CORS → 错误处理
  /chat /chat/stream      → LangGraph 图 (thread_id = tenant:user:session)
  /agent                  → ReAct/Plan 节点 + 工具
  /rag/query              → 检索→重排→生成(引用)
  /documents/upload /documents → 解析→分块→嵌入→pgvector
  /health /health/ready /metrics
领域核心 app/core
  langgraph/  StateGraph + 节点(react/plan/reflection) + 条件路由 + 递归上限
  rag/        retriever(向量+BM25+RRF) → reranker → generator
  memory/     short_term(Redis) + long_term(pgvector) + manager(接口对齐)
  tools/      registry(list_tool_names/invoke) + builtin
  guardrails/ 提示注入 / PII / 输出安全
基础设施 app/infrastructure
  llm/        model_router + circuit_breaker + tenacity 重试 + 超时/预算 + 降级
  vectordb/   VectorStore 端口 → pgvector(主) / pinecone(可选)
  embeddings/ 嵌入工厂
  db/         SQLAlchemy + Alembic + AsyncPostgresSaver + 连接池
  cache/      redis
  trace/      OTel GenAI semconv + Langfuse + Prometheus
```

## 2. 关键设计决策（ADR 摘要）

### ADR-1 编排引擎：LangGraph
- 用 `StateGraph` 把现有 ReAct/Plan/Reflection 包装为节点；状态 schema 用 `TypedDict`。
- 检查点用 `AsyncPostgresSaver`，按 `thread_id` 隔离与恢复多轮会话。
- 设递归上限与总超时预算，防失控循环。
- 现有手写 `orchestrator/react_agent/planner/reflection` 中的解析与提示逻辑尽量复用，外壳替换为 LangGraph。

### ADR-2 向量库：pgvector + 端口抽象
- 定义 `VectorStore` 抽象（`upsert/search/delete`）。
- pgvector 实现复用现有 Postgres；新增 `vector` 列与索引（HNSW/IVFFlat）。
- 保留 `MilvusManager` 作为可选实现，不在主链路启用；新增 Pinecone 适配器骨架（按配置切换）。
- `MultiRetriever` 的向量分支改为依赖 `VectorStore` 端口，BM25 分支保留。

### ADR-3 接口对齐（修复编排器装配）
- `ToolRegistry` 增加 `list_tool_names()` 与 `async invoke(name, args)`（委托给 `BaseTool.execute`）。
- 统一记忆接口：为编排器提供 `get_relevant()/append_turn()` 适配（在 `MemoryManager` 上补充），与现有 `get_context()/save()` 并存。

### ADR-4 追踪与可观测
- 替换坏掉的 `langfuse_exporter`：先以安全 no-op + 配置开关修复启动；后续采用 langchain `CallbackHandler`（参考标杆模板）。保留内存 `Tracer` 作为本地调试。
- 引入 OpenTelemetry GenAI 语义约定属性（`gen_ai.request.model`、`gen_ai.usage.*_tokens`、`gen_ai.response.finish_reasons` 等）。
- Prometheus 指标：延迟 p95、token、工具失败率、限流命中、评估通过率。

### ADR-5 安全
- 鉴权：API Key（服务间）或 JWT（用户态），租户上下文贯穿日志/指标/thread_id。
- 限流：slowapi（按 key/租户）。
- 护栏：输入做提示注入/PII 检测与清洗，输出做安全检查，结果记为独立 span。
- 密钥仅来自环境变量；遵循基座安全钩子（禁读 .env、禁打印密钥）。

## 3. 数据模型变更

- 复用现有 `conversations/messages/documents/document_chunks/trace_logs`。
- `document_chunks` 启用 `vector_id`，并在 pgvector 表（或同表 `vector` 列）存嵌入。
- 新增 LangGraph 检查点表（由 `AsyncPostgresSaver.setup()` 创建）。
- 鉴权相关：按需新增 `api_keys`（最小化，参考标杆模板）。
- 所有 schema 变更走 Alembic 迁移。

## 4. 配置（config.py / .env.example 补齐）

新增项：嵌入模型与维度、向量库类型与连接、Langfuse（host/keys/enabled）、鉴权（JWT secret / API keys）、限流阈值、超时与 token 预算、OTel exporter、Prometheus 开关、模型降级列表。

## 5. 横切关注点

- 韧性：tenacity 重试 + 现有 `CircuitBreaker` + 模型降级 + 总超时预算。
- 可观测：中间件注入 request_id；日志结构化；trace 贯穿。
- 部署：多阶段非 root Dockerfile；gunicorn(uvicorn worker) 多进程；优雅停机；连接池上限 < Postgres max_connections。

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LangGraph 迁移改动面大 | 复用现有节点逻辑，先打通最小图再扩展；保留旧实现到迁移完成 |
| 重依赖安装重（torch/sentence-transformers） | 嵌入走可配置后端，默认用轻量/远程嵌入；测试用 mock |
| pgvector 大规模性能 | 选 HNSW 索引 + 调参；端口抽象保留 Pinecone 退路 |
| 外部依赖（DB/Redis/向量库）联调成本 | 关键单测用 mock/伪实现；集成测试用容器；CI 分层 |
