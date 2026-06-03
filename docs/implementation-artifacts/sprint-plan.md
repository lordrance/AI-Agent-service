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
- [~] S0.4 配置补齐：Langfuse 已完成；embedding/向量库/鉴权/限流/超时预算随对应 Epic 增量补齐。

## Epic 1 — LangGraph + pgvector 打通四条主链路（P0）
- [ ] S1.1 `VectorStore` 端口 + pgvector 实现 + 嵌入工厂。验证：写入/检索 round-trip。
- [ ] S1.2 文档上传接 ETL→嵌入→pgvector（用 `on_chunks` 回调）。验证：上传后可检索。
- [ ] S1.3 LangGraph 对话图 + `AsyncPostgresSaver` 检查点。验证：多轮会话跨重启保持。
- [ ] S1.4 `/rag/query`：检索→重排→生成带引用。验证：黄金集冒烟。
- [ ] S1.5 `/agent`：ReAct/Plan 节点 + 内置工具，含递归/超时上限。验证：端到端跑通。

## Epic 2 — 测试与 CI/CD（P1）
- [ ] S2.1 单元测试：熔断/检索/记忆压缩/ReAct 解析/guardrails。
- [ ] S2.2 集成/端到端：httpx + 依赖容器(pg/redis) 跑四条链路。
- [ ] S2.3 GitHub Actions：ruff + mypy + pytest + RAG 评估门禁 + 镜像构建 + 依赖安全扫描。

## Epic 3 — 安全与多租户（P1）
- [ ] S3.1 API Key/JWT 鉴权 + 租户上下文贯穿。
- [ ] S3.2 slowapi 限流 + CORS + 安全响应头 + 请求体校验。
- [ ] S3.3 guardrails：提示注入检测 / PII 脱敏 / 输出安全（接链路 + span）。

## Epic 4 — 可观测性与韧性（P2）
- [ ] S4.1 OTel GenAI 语义约定埋点（模型/工具/检索 span + token/cost）。
- [ ] S4.2 Langfuse 接入完善；结构化日志带 trace/session/tenant id。
- [ ] S4.3 Prometheus 指标 + `/health/ready` 依赖探针。
- [ ] S4.4 统一超时/递归/token 预算 + tenacity 重试 + 模型降级。

## Epic 5 — 部署与扩展（P3）
- [ ] S5.1 生产 Dockerfile（多阶段/非 root/healthcheck）+ gunicorn 多 worker + 优雅停机。
- [ ] S5.2 compose/k8s 样例 + 连接池/PgBouncer 说明 + 配置/密钥管理。
- [ ] S5.3 基础负载冒烟 + 部署文档（扩缩容/回滚/迁移策略）。
