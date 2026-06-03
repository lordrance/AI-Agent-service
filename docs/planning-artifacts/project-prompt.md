# 项目提示词（Project Prompt）

- 版本: 1.0
- 状态: **已批准**（2026-06-03，按 project-plan-v2 执行）
- 适用范围: `project-python/` 及 `docs/planning-artifacts/`
- 关联: `prd.md`、`architecture.md`（v1 将随本提示词修订）

---

## 1. 项目是什么

**企业级 AI Agent 后端服务（Enterprise AI Agent API）** —— 一个仅供 HTTP 调用的 **纯后端** 项目，**不包含任何前端 UI**（无 React/Vue、无管理后台页面、无聊天窗口）。

对外提供四类能力，供业务系统、移动 App、脚本或其它服务集成：

1. **多轮对话**（LangGraph + 会话持久化）
2. **知识库文档入库与检索**（RAG）
3. **带工具调用的 Agent**（ReAct，可扩展工具）
4. **运维与安全**（健康检查、指标、鉴权、限流、护栏）

调用方通过 REST API（JSON）交互；流式对话使用 **SSE**，仍属 API 层能力，不算「前端产品」。

---

## 2. 项目用来做什么（价值主张）

| 角色 | 用途 |
|------|------|
| **业务集成方** | 把客服问答、内部知识库、自动化办公接到自有系统，无需自建 Agent 框架 |
| **平台工程师** | 获得可容器化、可观测、可多租户的后端模板，按端口扩展工具与检索策略 |
| **运维 / SRE** | 通过 `/health`、`/metrics`、Langfuse/OTel 监控延迟、Token 成本与依赖健康 |

典型场景：

- 上传制度/产品 PDF → 员工提问 → **带引用** 的答案（RAG）
- 客服机器人多轮对话，会话可恢复、按租户隔离
- 让 Agent 调用计算器、搜索、内部 API 完成「查数 + 汇总」类任务

---

## 3. 硬性约束（必须遵守）

1. **只做后端**：禁止在本仓库新增前端应用、静态站点、管理台 UI。允许 OpenAPI/Swagger 自动文档。
2. **向量库主选 Pinecone**：生产与默认配置以 **Pinecone** 为向量存储；保留 `VectorStore` 端口，`pgvector` 仅作**本地开发 / CI 降级**选项（无 Pinecone 密钥时可切回 pgvector）。
3. **密钥与配置**：仅环境变量 / K8s Secret，禁止硬编码；禁止在日志中打印 API Key。
4. **最小实现原则**：不引入与上述目标无关的抽象；每个 Epic 须有可验证的测试标准。
5. **中文优先**：面向维护者的文档、错误信息、冲刺故事用简体中文；代码标识符保持英文。

---

## 4. 技术栈（锁定）

| 层级 | 选型 |
|------|------|
| 语言 / 运行时 | Python 3.11+ |
| Web | FastAPI + Gunicorn(UvicornWorker) |
| Agent 编排 | LangGraph + `AsyncPostgresSaver`（检查点） |
| 关系库 | PostgreSQL 16（业务元数据、会话、文档块） |
| 向量库（主） | **Pinecone**（Serverless 或 Pod，按官方 Python SDK） |
| 向量库（备） | pgvector（同 Postgres，本地/CI） |
| 缓存 | Redis（短期记忆、可选限流存储） |
| 嵌入 | OpenAI 兼容 API（生产）；hash 嵌入（离线测试） |
| 鉴权 | API Key + JWT（租户上下文贯穿） |
| 可观测 | Prometheus、Langfuse（可选）、OpenTelemetry GenAI span（可选） |
| 部署 | Docker 多阶段镜像、Compose、K8s 样例 |

**明确弃用主链路**：Milvus 及 etcd/minio 栈不再作为默认 Compose 依赖（代码可保留遗留适配器但文档标注 deprecated）。

---

## 5. 功能需求（理想形态 — 相对当前实现的补齐目标）

### 5.1 对话 `/api/v1/chat` 与 `/api/v1/chat/stream`

- **统一引擎**：流式与非流式均经 **同一套 LangGraph 对话图**（或共享 `model_fn` + 检查点），禁止流式路径绕过护栏与租户隔离。
- **会话隔离**：`thread_id = {tenant_id}:{conversation_id}`，检查点存 Postgres。
- **流式**：SSE 输出；事件含 `trace_id`；支持优雅中断。
- **护栏**：用户消息入图前做注入检测 + PII 脱敏；输出流结束前做输出安全校验（流式可分块累积后校验或采用「违规即截断」策略，方案阶段定细节）。
- **可选**：意图识别结果作为 system 提示注入（保持现有 `IntentRecognizer`）。

### 5.2 文档 `/api/v1/documents/upload` 与 `/api/v1/documents`

- 解析（PDF/TXT 等）→ 分块 → 嵌入 → **写入 Pinecone**（默认），元数据与 `vector_id` 写入 Postgres `documents` / `document_chunks`。
- **租户隔离**：Pinecone 使用 **namespace = tenant_id**（或 metadata filter `tenant_id` + 统一 index），禁止跨租户检索。
- 列表、删除（含向量删除）API；删除文档时同步删 Pinecone 向量。
- 上传大小、MIME 白名单、分块参数可配置。

### 5.3 RAG `/api/v1/rag/query`

- **混合检索（必须接入主链路）**：
  - **向量路**：Pinecone（经 `VectorStore`）
  - **关键词路**：BM25（语料来自当前租户已入库分块，内存索引或 Postgres 全文检索二选一，方案阶段选定）
  - **融合**：RRF（Reciprocal Rank Fusion）
- **可选重排**：Cross-Encoder（`rerank_enabled`，默认关，避免 CI 强依赖 torch）
- **生成**：带引用 `[1][2]`；无 LLM Key 时降级为仅返回 `raw_contexts`
- **评估**：`scripts/eval_rag_golden.py` 必须调用 **真实 `RagService`**，CI 设 `fail-under` 阈值

### 5.4 Agent `/api/v1/agent`

- ReAct 循环 + `ToolRegistry`；`max_steps`、总超时、递归上限。
- **记忆（补齐）**：接入 `MemoryManager`（Redis 短期 + Pinecone/pgvector 长期召回），按 `session_id` / 租户隔离。
- **护栏**：与 chat/rag 一致。
- **可扩展**：新工具通过注册表插件式添加（文档说明约定）。

### 5.5 横切能力（在 Epic 0–5 基础上增强）

| 能力 | 要求 |
|------|------|
| 鉴权 | `AUTH_ENABLED` 生产默认 true；健康检查与 metrics 豁免 |
| 限流 | 按租户 + IP；超限入 Prometheus |
| 可观测 | 全链路 `trace_id`；Langfuse 导出含 tenant/session；OTel 可选接 OTLP Exporter |
| 韧性 | 已有 ModelRouter 降级/重试/熔断；Agent/Chat 统一超时预算配置 |
| 部署 | Compose 默认 **Postgres + Redis + App**；Pinecone 云服务；文档说明索引创建与维度一致性 |

---

## 6. 非功能需求

- **可用性**：Pinecone/Postgres/Redis 不可用时 `/health/ready` 为 degraded；核心写操作失败返回明确 5xx/503。
- **性能**：单请求 P95 目标由部署方自定；代码须避免 N+1 与无界内存（BM25 索引按租户懒加载 + 上限）。
- **安全**：OWASP API 基础项；输入长度限制；CORS 生产禁止 `*`（可配置）。
- **可测试性**：单元测试不依赖 Pinecone 真实例（mock `VectorStore`）；集成测试可选 Pinecone sandbox 或 pgvector 降级。
- **可维护性**：全量 `mypy app` 在某一 Epic 结束前清零或纳入 CI 门禁。

---

## 7. 明确不做（Out of Scope）

- 任何前端 UI、移动端 App、微信小程序
- 模型训练 / 微调 / RLHF
- 多模态（图片/语音）除非后续单独立项
- 复杂工作流编排 UI、低代码画布
- 内置用户注册登录页面（仅 API 鉴权，账号体系由调用方负责）

---

## 8. 验收标准（Definition of Done — 理想态）

1. `pytest` 全绿；新增 Pinecone 适配器与混合 RAG 有单测 + 集成测。
2. 默认 `VECTOR_STORE=pinecone` 时，上传文档 → `/rag/query` 可检索命中；租户 A 无法检索租户 B 数据。
3. `/chat` 与 `/chat/stream` 行为一致（同一会话 thread、同样护栏策略）。
4. `/agent` 在开启记忆时可引用同会话历史（至少短期记忆）。
5. RAG 黄金集评估走真实管道，CI `fail-under ≥ 0.8`（样本集可扩充）。
6. `mypy app` 无错误；`ruff` 干净。
7. README + `docs/deployment.md` + `.env.example` 与 Pinecone 配置一致；Compose 无 Milvus 必选依赖。
8. 生产镜像可构建；`scripts/smoke_deploy.sh` 通过。

---

## 9. 给 AI / 开发者的执行口令（审核通过后使用）

当你在本仓库写代码时，请默认：

1. 先读 `docs/planning-artifacts/project-prompt.md`（本文件）与 `project-plan-v2.md`（项目方案）。
2. **不要**新增前端；**不要**把 Milvus 接回主链路。
3. 向量相关改动必须走 `VectorStore` 端口；生产默认 Pinecone，实现 namespace/tenant 隔离。
4. RAG 必须实现「向量 + BM25 + RRF」主路径，而非仅 pgvector 单向量检索。
5. 每个故事：先写失败测试 → 实现 → 跑通 → 更新 sprint 状态；改动保持最小 diff。
6. 配置项同步 `.env.example` 与 `app/config.py`；文档用简体中文。

---

## 10. 术语表

| 术语 | 含义 |
|------|------|
| RAG | 检索增强生成：先查知识库再让 LLM 回答 |
| ReAct | 推理 + 行动交替的 Agent 模式 |
| RRF | 多路检索结果融合算法 |
| namespace | Pinecone 内逻辑隔离单元，本项目中对齐 `tenant_id` |
| thread_id | LangGraph 会话键，格式 `tenant_id:conversation_id` |
| 护栏 | 对输入/输出做安全与合规检测 |

---

## 11. 待你确认的问题（审核时请注明）

1. **Pinecone 套餐**：Serverless（按量）还是固定 Pod？是否已有账号与 index 命名规范？
2. **BM25 语料来源**：优先「Postgres 存全文 + 查询时建索引」还是「上传时写 Redis/内存」？
3. **流式护栏**：接受「流结束后统一校验」还是必须「逐 token 检测」（后者复杂度高）？
4. **pgvector 定位**：仅本地/CI，还是生产也要双写（一般不建议）？

审核通过后，以 **`project-plan-v2.md`** 为实施顺序依据开始编码。
