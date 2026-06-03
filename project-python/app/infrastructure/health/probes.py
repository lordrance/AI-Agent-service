# -*- coding: utf-8 -*-
"""就绪探针：PostgreSQL / Redis / 向量库连通性。"""

from __future__ import annotations

import asyncpg
import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.infrastructure.vectordb.base import VectorStore
from app.infrastructure.vectordb.pgvector_store import PgVectorStore, _to_asyncpg_dsn


async def check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("数据库探针失败: {}", exc)
        return False


async def check_redis(settings: Settings) -> bool:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.warning("Redis 探针失败: {}", exc)
        return False
    finally:
        await client.aclose()


async def check_vector_store(vector_store: VectorStore) -> bool:
    if isinstance(vector_store, PgVectorStore):
        try:
            dsn = _to_asyncpg_dsn(vector_store._dsn)  # noqa: SLF001
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute("SELECT 1")
                ext = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1"
                )
                return ext is not None
            finally:
                await conn.close()
        except Exception as exc:
            logger.warning("向量库探针失败: {}", exc)
            return False
    return True
