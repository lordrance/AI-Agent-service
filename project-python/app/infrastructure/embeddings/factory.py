"""嵌入器工厂：按配置返回具体后端实例。"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger

from app.config import get_settings
from app.infrastructure.embeddings.base import Embedder
from app.infrastructure.embeddings.hashing import HashingEmbedder


@lru_cache
def get_embedder() -> Embedder:
    """根据 `settings.embedding_backend` 构造嵌入器（带进程级缓存）。"""
    settings = get_settings()
    backend = settings.embedding_backend.lower().strip()

    if backend == "openai":
        from app.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        logger.info("使用 OpenAI 嵌入后端 model={}", settings.embedding_model)
        return OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            base_url=settings.openai_api_base,
        )

    if backend != "hash":
        logger.warning("未知 embedding_backend={}，回退为 hash", backend)
    logger.info("使用本地哈希嵌入后端 dim={}", settings.embedding_dim)
    return HashingEmbedder(dim=settings.embedding_dim)
