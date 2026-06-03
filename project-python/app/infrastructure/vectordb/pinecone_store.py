"""Pinecone 向量库实现（托管 Serverless / Pod）。"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.infrastructure.vectordb.base import VectorHit, VectorRecord, VectorStore


class PineconeVectorStore(VectorStore):
    """Pinecone 向量库：按 namespace 隔离租户。"""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        *,
        host: str = "",
        metric: str = "cosine",
    ) -> None:
        if not api_key:
            raise ValueError("PINECONE_API_KEY 未配置")
        if not index_name:
            raise ValueError("PINECONE_INDEX 未配置")
        self._api_key = api_key
        self._index_name = index_name
        self._host = host.strip()
        self._metric = metric
        self._index: Any = None
        self._client: Any = None

    def _get_index(self) -> Any:
        if self._index is not None:
            return self._index
        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise RuntimeError("请安装 pinecone: pip install pinecone") from exc

        self._client = Pinecone(api_key=self._api_key)
        if self._host:
            self._index = self._client.Index(self._index_name, host=self._host)
        else:
            self._index = self._client.Index(self._index_name)
        logger.info("Pinecone 索引已连接 index={}", self._index_name)
        return self._index

    @staticmethod
    def _ns(namespace: str | None) -> str:
        return namespace or "default"

    @staticmethod
    def _record_to_vector(rec: VectorRecord, namespace: str | None) -> dict[str, Any]:
        meta = dict(rec.metadata or {})
        if rec.document_id:
            meta["document_id"] = rec.document_id
        if namespace:
            meta["tenant_id"] = namespace
        # Pinecone metadata 需存文本供检索结果展示（有长度上限，截断）
        meta["content"] = (rec.content or "")[:40000]
        return {
            "id": rec.id,
            "values": rec.embedding,
            "metadata": meta,
        }

    async def upsert(
        self,
        records: list[VectorRecord],
        *,
        namespace: str | None = None,
    ) -> list[str]:
        if not records:
            return []
        index = self._get_index()
        ns = self._ns(namespace)
        vectors = [self._record_to_vector(r, namespace) for r in records]

        def _sync() -> None:
            index.upsert(vectors=vectors, namespace=ns)

        try:
            await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pinecone upsert 失败 namespace={}", ns)
            raise RuntimeError(f"Pinecone 向量写入失败: {exc}") from exc
        return [r.id for r in records]

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        *,
        namespace: str | None = None,
    ) -> list[VectorHit]:
        index = self._get_index()
        ns = self._ns(namespace)

        def _sync() -> Any:
            return index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=ns,
                include_metadata=True,
            )

        try:
            resp = await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pinecone 检索失败 namespace={}", ns)
            raise RuntimeError(f"Pinecone 向量检索失败: {exc}") from exc

        hits: list[VectorHit] = []
        for match in getattr(resp, "matches", []) or []:
            meta = dict(match.metadata or {}) if match.metadata else {}
            doc_id = meta.pop("document_id", None)
            content = str(meta.pop("content", "") or meta.pop("text", "") or "")
            score = float(match.score or 0.0)
            hits.append(
                VectorHit(
                    id=str(match.id),
                    content=content,
                    score=score,
                    document_id=str(doc_id) if doc_id else None,
                    metadata=meta,
                )
            )
        return hits

    async def delete(self, ids: list[str], *, namespace: str | None = None) -> None:
        if not ids:
            return
        index = self._get_index()
        ns = self._ns(namespace)

        def _sync() -> None:
            index.delete(ids=ids, namespace=ns)

        try:
            await asyncio.to_thread(_sync)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pinecone 删除失败 namespace={}", ns)
            raise RuntimeError(f"Pinecone 向量删除失败: {exc}") from exc

    async def ping(self) -> bool:
        """就绪探针：describe_index_stats。"""
        try:
            index = self._get_index()

            def _sync() -> None:
                index.describe_index_stats()

            await asyncio.to_thread(_sync)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pinecone 探针失败: {}", exc)
            return False

    async def close(self) -> None:
        self._index = None
        self._client = None
