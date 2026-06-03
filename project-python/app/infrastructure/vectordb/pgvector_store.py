"""pgvector 向量库实现（基于 asyncpg）。

表结构由 Alembic 迁移创建（含 `vector(dim)` 列与 HNSW 索引）。本实现负责
连接池管理、批量 upsert、相似度检索与删除，并将距离统一换算为「score 越大越相关」。
"""

from __future__ import annotations

import json
import re
from typing import Any

import asyncpg
from loguru import logger
from pgvector.asyncpg import register_vector

from app.infrastructure.vectordb.base import VectorHit, VectorRecord, VectorStore

# metric -> (距离算子, 索引 ops)
_METRIC_OPS: dict[str, str] = {
    "cosine": "<=>",
    "l2": "<->",
    "ip": "<#>",
}


def _to_asyncpg_dsn(url: str) -> str:
    """将 SQLAlchemy 风格 URL 规整为 asyncpg 可用 DSN。"""
    dsn = re.sub(r"\+asyncpg|\+psycopg2|\+psycopg", "", url)
    return dsn


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector 向量库。"""

    def __init__(
        self,
        dsn: str,
        table: str,
        dim: int,
        metric: str = "cosine",
    ) -> None:
        self._dsn = _to_asyncpg_dsn(dsn)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError(f"非法表名: {table}")
        self._table = table
        self._dim = dim
        self._metric = metric if metric in _METRIC_OPS else "cosine"
        self._op = _METRIC_OPS[self._metric]
        self._pool: asyncpg.Pool | None = None

    async def _ensure_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=1,
                max_size=5,
                init=self._init_conn,
            )
            logger.info("pgvector 连接池已建立 table={}", self._table)
        return self._pool

    @staticmethod
    async def _init_conn(conn: asyncpg.Connection) -> None:
        await register_vector(conn)

    def _score(self, distance: float) -> float:
        """把距离换算为 score（越大越相关）。"""
        if self._metric == "cosine":
            return 1.0 - distance
        if self._metric == "ip":
            # <#> 返回负内积，取反得到内积本身
            return -distance
        # l2：距离越小越相关
        return -distance

    async def upsert(self, records: list[VectorRecord]) -> list[str]:
        if not records:
            return []
        pool = await self._ensure_pool()
        sql = (
            f"INSERT INTO {self._table} (id, document_id, content, metadata, embedding) "
            f"VALUES ($1, $2, $3, $4::jsonb, $5) "
            f"ON CONFLICT (id) DO UPDATE SET "
            f"document_id = EXCLUDED.document_id, content = EXCLUDED.content, "
            f"metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding"
        )
        rows = [
            (
                r.id,
                r.document_id,
                r.content,
                json.dumps(r.metadata or {}, ensure_ascii=False),
                r.embedding,
            )
            for r in records
        ]
        try:
            async with pool.acquire() as conn:
                await conn.executemany(sql, rows)
        except Exception as exc:  # noqa: BLE001
            logger.exception("pgvector upsert 失败 table={}", self._table)
            raise RuntimeError(f"向量写入失败: {exc}") from exc
        return [r.id for r in records]

    async def search(self, query_embedding: list[float], top_k: int = 10) -> list[VectorHit]:
        pool = await self._ensure_pool()
        sql = (
            f"SELECT id, document_id, content, metadata, "
            f"embedding {self._op} $1 AS distance "
            f"FROM {self._table} ORDER BY embedding {self._op} $1 ASC LIMIT $2"
        )
        try:
            async with pool.acquire() as conn:
                records = await conn.fetch(sql, query_embedding, top_k)
        except Exception as exc:  # noqa: BLE001
            logger.exception("pgvector 检索失败 table={}", self._table)
            raise RuntimeError(f"向量检索失败: {exc}") from exc

        hits: list[VectorHit] = []
        for row in records:
            meta: dict[str, Any] = {}
            raw_meta = row["metadata"]
            if raw_meta:
                meta = raw_meta if isinstance(raw_meta, dict) else json.loads(raw_meta)
            hits.append(
                VectorHit(
                    id=row["id"],
                    content=row["content"],
                    score=self._score(float(row["distance"])),
                    document_id=row["document_id"],
                    metadata=meta,
                )
            )
        return hits

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        pool = await self._ensure_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute(f"DELETE FROM {self._table} WHERE id = ANY($1)", ids)
        except Exception as exc:  # noqa: BLE001
            logger.exception("pgvector 删除失败 table={}", self._table)
            raise RuntimeError(f"向量删除失败: {exc}") from exc

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
