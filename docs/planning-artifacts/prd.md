# PRD — 企业级 AI Agent 服务生产化改造

- 版本: 0.1
- 状态: Draft（执行中）
- 作者: AI 平台工程（受 lordrance 委托）
- 关联代码: `project-python/`

## 1. 背景与问题

`project-python` 是一套企业级 AI Agent 服务骨架，单模块质量较高（熔断器、混合检索、ReAct 解析、短期记忆压缩等），但**组件之间未集成，且当前无法启动**。本 PRD 的目标是按 2026 年工业级标准，将其改造成**可上线扛真实流量**的生产服务。

### 当前致命缺陷（P0）
1. `app/api/routes/chat.py` 导入不存在的 `app.infrastructure.trace.langfuse_exporter` → `import app.main` 失败，服务无法启动。
2. 无数据库迁移（Alembic），表从未创建 → 文档相关接口运行即报错。
3. 核心组件（编排器 / RAG / 记忆）未被任何端点调用，是死代码。
4. 编排器协议（`list_tool_names`/`invoke`/`get_relevant`/`append_turn`）与具体类（`ToolRegistry`/`MemoryManager`）方法签名不匹配，无法装配。
5. RAG 入库链路断裂：文档上传只写 Postgres 分块，从不向量化、从不写向量库；无 `/rag` 查询端点。

## 2. 目标与非目标

### 目标
- P0 让服务可启动；用 **LangGraph + pgvector** 打通四条主链路：对话、文档入库、RAG 问答、Agent 工具调用。
- P1 测试金字塔（单元/集成/端到端）+ GitHub Actions CI/CD 门禁（lint + type + test + RAG 评估 + 镜像构建 + 安全扫描）。
- P1 安全与多租户：API Key/JWT 鉴权、slowapi 限流、CORS、密钥仅走环境变量、输入校验。
- P2 可观测性与韧性：OpenTelemetry GenAI 语义约定埋点、Langfuse 接入、结构化日志带 trace/session/tenant id、统一超时/递归/token 预算、重试+熔断+模型降级、`/health/ready` 依赖探针、Prometheus 指标。
- P2 安全护栏：提示注入检测、PII 脱敏、输出安全检查（独立 span）。
- P3 部署与扩展：生产 Dockerfile、gunicorn/uvicorn 多 worker、连接池/PgBouncer 说明、优雅停机、compose/k8s 样例、基础负载冒烟。

### 非目标
- 不做前端 UI（保留 Playwright 占位但不启用）。
- 不引入与目标无关的抽象/配置项（遵循 CLAUDE.md「最小实现」）。
- 不在本轮做大规模分布式训练/微调。

## 3. 技术决策（已锁定）

| 维度 | 决策 | 理由 |
|------|------|------|
| Agent 引擎 | LangGraph `StateGraph` + Postgres 检查点 | 2026 工业标准，状态可持久化/可重放/多 worker 共享 |
| 向量库 | pgvector 主用，`VectorStore` 端口抽象 + Pinecone 可切换适配器 | 单库省运维，够扛千万级；保留托管云退路 |
| 定位 | 真生产服务 | 鉴权/限流/可观测/韧性/护栏/容器化全部必做 |
| 流程 | BMAD 故事逐个推进；故事内技术选项由执行者自决，不打断用户 | 用户最新授权 |
| 参考实现 | `wassim249/fastapi-langgraph-agent-production-ready-template` | 运维层（鉴权/限流/可观测/评估/CI/Docker）的标杆，移植模式而非合并仓库 |

## 4. 用户与主要用例

- **集成方/调用方**：通过 HTTP API 发起对话、上传知识文档、做 RAG 问答、触发 Agent 工具任务。
- **运维**：通过 `/health`、`/health/ready`、`/metrics` 与 Langfuse/Grafana 观测系统健康与成本。
- **平台开发**：基于清晰的领域核心与基础设施分层扩展工具、检索策略与模型。

## 5. 功能需求（按主链路）

1. **对话** `/chat`、`/chat/stream`：经 LangGraph 图执行，按 `thread_id=tenant:user:session` 隔离会话，支持流式（SSE）。
2. **文档入库** `/documents/upload`、`/documents`：解析→分块→嵌入→写入 pgvector，落库元数据与 `vector_id`。
3. **RAG 问答** `/rag/query`：混合检索（向量+BM25+RRF）→ 重排 → 生成（带引用）。
4. **Agent 工具** `/agent`：ReAct/Plan 节点 + 内置工具（计算器/搜索），含递归/超时上限。

## 6. 非功能需求

- 可用性：依赖不可用时优雅降级，关键路径有超时与熔断。
- 安全：鉴权、限流、输入清洗、密钥不落盘不打印。
- 可观测：每条请求可追踪到 trace/session/tenant，含 token/cost 指标。
- 可维护：测试覆盖关键路径，CI 全绿方可合并。
- 可部署：容器化、可水平扩展、优雅停机、迁移可控。

## 7. 验收标准（Definition of Done）

- `python scripts/health-check.py` 绿；`uvicorn app.main:app` 可启动。
- 四条主链路有端到端测试且 CI 全绿。
- 鉴权/限流生效，非法/超额请求被正确拒绝且有测试覆盖。
- RAG 黄金集评估接入真实管道并设 CI 阈值门禁。
- 关键路径有 OTel span 与 Prometheus 指标；Langfuse 可见 trace。
- 生产镜像可构建、可优雅停机；README/.env.example 与实际配置一致、无悬空引用。

## 8. 里程碑

1. M1 能跑通：Epic 0 + Epic 1。
2. M2 可信赖：Epic 2 + Epic 3。
3. M3 可运维：Epic 4。
4. M4 可上线：Epic 5。
