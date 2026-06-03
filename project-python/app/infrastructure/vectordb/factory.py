"""向量库工厂：按配置构造 VectorStore 实例。

不做进程级缓存：asyncpg 连接池与事件循环绑定，应由调用方（如应用 lifespan）
负责单例化与生命周期管理，避免跨事件循环复用。
"""

from __future__ import annotations

from app.config import get_settings
from app.infrastructure.vectordb.base import VectorStore
from app.infrastructure.vectordb.pgvector_store import PgVectorStore


def build_vector_store() -> VectorStore:
    """根据 `settings.vector_store` 构造向量库实现。"""
    settings = get_settings()
    kind = settings.vector_store.lower().strip()
    if kind == "pinecone":
        raise NotImplementedError(
            "Pinecone 适配器尚未实现（VectorStore 端口已预留，按需补充）"
        )
    return PgVectorStore(
        dsn=settings.database_url,
        table=settings.vector_table,
        dim=settings.embedding_dim,
        metric=settings.vector_metric,
    )
