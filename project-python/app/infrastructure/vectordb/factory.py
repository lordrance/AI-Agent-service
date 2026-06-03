"""向量库工厂：按配置构造 VectorStore 实例。

不做进程级缓存：asyncpg 连接池与事件循环绑定，应由调用方（如应用 lifespan）
负责单例化与生命周期管理，避免跨事件循环复用。
"""

from __future__ import annotations

from app.config import get_settings
from app.infrastructure.vectordb.base import VectorStore
from app.infrastructure.vectordb.pgvector_store import PgVectorStore
from app.infrastructure.vectordb.pinecone_store import PineconeVectorStore


def build_vector_store() -> VectorStore:
    """根据 `settings.vector_store` 构造向量库实现。"""
    settings = get_settings()
    kind = settings.vector_store.lower().strip()
    if kind == "pinecone":
        if not settings.pinecone_api_key:
            raise ValueError("VECTOR_STORE=pinecone 但未配置 PINECONE_API_KEY")
        return PineconeVectorStore(
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index,
            host=settings.pinecone_host,
            metric=settings.vector_metric,
        )
    return PgVectorStore(
        dsn=settings.database_url,
        table=settings.vector_table,
        dim=settings.embedding_dim,
        metric=settings.vector_metric,
    )
