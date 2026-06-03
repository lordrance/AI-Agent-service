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

    langfuse_enabled: bool = Field(default=False, description="是否启用 Langfuse 追踪导出")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse Host",
    )
    langfuse_public_key: str = Field(default="", description="Langfuse Public Key")
    langfuse_secret_key: str = Field(default="", description="Langfuse Secret Key")


@lru_cache
def get_settings() -> Settings:
    return Settings()
