# 冲刺计划与故事清单

- 关联: `docs/planning-artifacts/prd.md`、`architecture.md`
- 流程: BMAD 逐故事推进；每个故事先定可验证标准/写测试 → 实现 → 跑通 → 提交。
- 授权: 故事内技术选项由执行者自决，不打断用户（仅高危点提示）。

## 状态图例
- [ ] 待办  · [~] 进行中  · [x] 完成  · [!] 受阻

## Epic 0 — 起死回生（P0）✅ 已完成
- [x] S0.1 新增安全 `langfuse_exporter`（默认关闭=no-op）+ Langfuse 配置。验证：`import app.main` 成功（实测通过）。
- [x] S0.2 引入 Alembic + 初始迁移。验证：对真实 PostgreSQL 16 实测 `upgrade head` 建 5 表、`downgrade base` 清空。
- [x] S0.3 对齐 `ToolRegistry`/`MemoryManager` 与编排器协议。验证：单测 3 passed、ruff 干净。
- [x] S0.4 配置补齐：Langfuse、embedding/向量库、鉴权/限流/护栏/CORS 已写入 `config.py` 与 `.env.example`。

## Epic 1 — LangGraph + pgvector 打通四条主链路（P0）✅ 已完成
- [x] S1.1 `VectorStore` 端口 + pgvector 实现 + 嵌入工厂。验证：真实 PG+pgvector 写入/检索 round-trip（RAG 文档 Top-1）。
- [x] S1.2 文档上传接 ETL→嵌入→pgvector。验证：集成测试上传→嵌入→入库，向量数=分块数。
- [x] S1.3 LangGraph 对话图 + `AsyncPostgresSaver` 检查点；/chat 接入。验证：跨实例（模拟重启）会话历史保持。
- [x] S1.4 `/rag/query`：检索→（可选）重排→生成带引用。验证：检索排序 + 引用解析单测。
- [x] S1.5 `/agent`：ReActAgent + 内置工具，含 max_steps 递归上限与总超时。验证：工具调用与防失控单测。

> 说明：重排（Cross-Encoder）默认关闭（需 sentence-transformers）；嵌入默认用本地哈希后端（离线可跑），生产切 openai。

## Epic 2 — 测试与 CI/CD（P1）✅ 已完成
- [x] S2.1 单元测试：熔断/检索/记忆压缩/ReAct 解析/guardrails。验证：`tests/test_s2_1_*.py` 全通过。
- [x] S2.2 集成/端到端：httpx + ASGI lifespan + 四条链路。验证：`tests/test_s2_2_e2e_api.py`（DB 不可达时自动 skip）。
- [x] S2.3 GitHub Actions：`.github/workflows/ci.yml` — ruff + 增量 mypy + pytest + RAG 黄金集门禁 + Docker 构建 + pip-audit。

> 说明：全量 `mypy app` 尚有历史类型债（7 文件）；CI 当前门禁 `guardrails` + `circuit_breaker`，待后续专项清理后扩至全库。

## Epic 3 — 安全与多租户（P1）✅ 已完成
- [x] S3.1 API Key/JWT 鉴权 + 租户上下文贯穿。验证：`X-API-Key` / Bearer JWT → `X-Tenant-Id`；LangGraph `thread_id` 为 `tenant:session`。
- [x] S3.2 slowapi 限流 + CORS + 安全响应头 + Content-Length 请求体上限 + Pydantic 字段长度。验证：`tests/test_s3_2_security.py`。
- [x] S3.3 guardrails：输入/输出接入 `/chat` `/rag/query` `/agent`，Tracer `guardrails.*` span。验证：`tests/test_s3_3_guardrails_api.py`。

> 说明：`AUTH_ENABLED=false`（默认）时匿名访问，便于本地/CI；生产设 `AUTH_ENABLED=true` 并配置 `API_KEYS` 或 `JWT_SECRET`。

## Epic 4 — 可观测性与韧性（P2）✅ 已完成
- [x] S4.1 OTel GenAI 语义约定埋点（`genai_otel.py`：chat/retrieval/tool + token）。验证：`tests/test_s4_1_otel.py`。
- [x] S4.2 Langfuse 导出含 tenant/session/request；loguru 结构化字段。验证：导出 metadata + 日志 patcher。
- [x] S4.3 Prometheus `/api/v1/metrics` + HTTP/LLM/工具指标；`/health/ready` 检查 DB/Redis/pgvector。验证：`tests/test_s4_3_observability.py`。
- [x] S4.4 `ModelRouter`：tenacity 重试、调用超时、max_tokens 上限、`LLM_FALLBACK_MODELS` 降级链。验证：`tests/test_s4_4_resilience.py`。

## Epic 5 — 部署与扩展（P3）
- [ ] S5.1 生产 Dockerfile（多阶段/非 root/healthcheck）+ gunicorn 多 worker + 优雅停机。
- [ ] S5.2 compose/k8s 样例 + 连接池/PgBouncer 说明 + 配置/密钥管理。
- [ ] S5.3 基础负载冒烟 + 部署文档（扩缩容/回滚/迁移策略）。
