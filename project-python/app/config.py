"""应用配置：基于 pydantic-settings，支持环境变量与 .env 文件。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="enterprise-ai-agent", description="服务名称")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    api_prefix: str = Field(default="/api/v1", description="API 前缀")
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, description="监听端口")

    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI 兼容 API Base",
    )
    openai_model: str = Field(default="gpt-4o-mini", description="默认对话模型")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db",
        description="SQLAlchemy 异步数据库 URL（推荐 postgresql+asyncpg）",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    milvus_host: str = Field(default="localhost", description="Milvus 主机")
    milvus_port: int = Field(default=19530, description="Milvus 端口")
    milvus_user: str = Field(default="", description="Milvus 用户名")
    milvus_password: str = Field(default="", description="Milvus 密码")
    milvus_collection_name: str = Field(
        default="agent_knowledge",
        description="默认向量集合名",
    )

    log_level: str = Field(default="INFO", description="日志级别")

    # 嵌入与向量库（Epic 1）
    embedding_backend: str = Field(
        default="hash",
        description="嵌入后端：hash（本地确定性，无需密钥/可离线）| openai（调用嵌入 API）",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="openai 后端使用的嵌入模型名",
    )
    embedding_dim: int = Field(
        default=1536,
        description="嵌入维度（须与向量库迁移中的 vector(dim) 一致；改动需新迁移）",
    )
    vector_store: str = Field(default="pgvector", description="向量库实现：pgvector | pinecone")
    vector_table: str = Field(default="knowledge_vectors", description="pgvector 表名")
    vector_metric: str = Field(default="cosine", description="相似度度量：cosine | l2 | ip")

    agent_max_steps: int = Field(default=8, description="ReAct Agent 最大步数（递归上限）")
    agent_timeout_seconds: float = Field(default=60.0, description="Agent 单次运行总超时（秒）")

    rag_top_k: int = Field(default=5, description="RAG 检索返回的上下文数量")
    rerank_enabled: bool = Field(
        default=False,
        description="是否启用 Cross-Encoder 重排（需 sentence-transformers）",
    )
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="重排模型名",
    )

    langfuse_enabled: bool = Field(default=False, description="是否启用 Langfuse 追踪导出")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse Host",
    )
    langfuse_public_key: str = Field(default="", description="Langfuse Public Key")
    langfuse_secret_key: str = Field(default="", description="Langfuse Secret Key")

    # Epic 3 — 鉴权与多租户
    auth_enabled: bool = Field(
        default=False,
        description="是否启用 API Key / JWT 鉴权（未启用时租户为 anonymous）",
    )
    api_keys: str = Field(
        default="",
        description="API Key 映射：tenant:secret 或 secret（默认租户 default），逗号分隔",
    )
    jwt_secret: str = Field(default="", description="JWT HS256 签名密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT 算法")
    jwt_audience: str = Field(default="", description="JWT aud 校验（空则跳过）")

    # 限流、CORS、请求边界
    rate_limit_enabled: bool = Field(default=True, description="是否启用 slowapi 限流")
    rate_limit_default: str = Field(default="60/minute", description="默认限流规则")
    rate_limit_storage_uri: str = Field(
        default="",
        description="slowapi 存储 URI（空=进程内存；生产可设 redis://）",
    )
    cors_origins: str = Field(
        default="*",
        description="CORS 允许来源，逗号分隔；* 表示全部",
    )
    max_request_body_bytes: int = Field(
        default=10_485_760,
        description="请求体最大字节（Content-Length）",
    )
    max_text_field_length: int = Field(
        default=32_000,
        description="单条文本字段最大字符（消息/查询等）",
    )

    # 护栏
    guardrails_enabled: bool = Field(default=True, description="是否在 API 链路启用护栏")

    # Epic 4 — 可观测性与韧性
    otel_enabled: bool = Field(default=False, description="是否启用 OpenTelemetry GenAI span")
    otel_service_name: str = Field(default="enterprise-ai-agent", description="OTel 服务名")
    prometheus_enabled: bool = Field(default=True, description="是否暴露 /metrics")
    llm_timeout_seconds: float = Field(default=60.0, description="单次 LLM HTTP 调用超时（秒）")
    llm_max_tokens_per_request: int | None = Field(
        default=4096,
        description="单次请求 max_tokens 上限（None 表示不限制）",
    )
    llm_retry_max_attempts: int = Field(default=3, description="可重试错误的最大尝试次数")
    llm_fallback_models: str = Field(
        default="",
        description="降级模型列表（逗号分隔），优先级低于 OPENAI_MODEL",
    )
    circuit_breaker_failure_threshold: int = Field(default=5, description="熔断失败阈值")
    circuit_breaker_recovery_timeout: float = Field(
        default=60.0,
        description="熔断恢复等待（秒）",
    )

    def fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    # Epic 5 — 生产部署
    run_migrations_on_startup: bool = Field(
        default=True,
        description="容器启动时是否执行 alembic upgrade head",
    )
    gunicorn_workers: int | None = Field(
        default=None,
        description="Gunicorn worker 数（None 时由 gunicorn_conf 按 CPU 计算）",
    )
    gunicorn_graceful_timeout: int = Field(default=30, description="Gunicorn 优雅停机等待（秒）")
    gunicorn_timeout: int = Field(default=120, description="Gunicorn worker 请求超时（秒）")


@lru_cache
def get_settings() -> Settings:
    return Settings()
