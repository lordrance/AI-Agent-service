"""混合检索：VectorStore 向量路 + 租户 BM25 + RRF 融合。"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.core.rag.bm25_registry import TenantBm25Registry
from app.core.rag.retriever import MultiRetriever
from app.infrastructure.embeddings.base import Embedder
from app.infrastructure.vectordb.base import VectorStore
from app.models.schemas import RetrievalResult


class HybridRetriever:
    """生产 RAG 主检索器（不依赖 Milvus）。"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        bm25_registry: TenantBm25Registry,
        *,
        rrf_k: int = 60,
    ) -> None:
        self._vs = vector_store
        self._embedder = embedder
        self._bm25 = bm25_registry
        self._rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        vec_task = self._vector_search(query, tenant_id, top_k)
        kw_task = self._keyword_search(query, tenant_id, top_k)
        vec_res, kw_res = await asyncio.gather(vec_task, kw_task, return_exceptions=True)

        lists: list[list[RetrievalResult]] = []
        if isinstance(vec_res, list) and vec_res:
            lists.append(vec_res)
        elif isinstance(vec_res, Exception):
            logger.error("向量检索失败: {}", vec_res)
        if isinstance(kw_res, list) and kw_res:
            lists.append(kw_res)
        elif isinstance(kw_res, Exception):
            logger.error("BM25 检索失败: {}", kw_res)

        if not lists:
            if isinstance(vec_res, Exception):
                raise vec_res
            if isinstance(kw_res, Exception):
                raise kw_res
            return []

        if len(lists) == 1:
            return lists[0][:top_k]

        helper = MultiRetriever(milvus_client=None, embedding_model=None)
        helper._rrf_k = self._rrf_k
        return helper._rrf_fuse(lists, top_k)

    async def _vector_search(
        self, query: str, tenant_id: str, top_k: int
    ) -> list[RetrievalResult]:
        vector = await asyncio.to_thread(self._embedder.embed_query, query)
        hits = await self._vs.search(vector, top_k=top_k, namespace=tenant_id)
        return [
            RetrievalResult(
                id=h.id,
                content=h.content,
                score=h.score,
                metadata={**h.metadata, "document_id": h.document_id},
                source="vector",
            )
            for h in hits
        ]

    async def _keyword_search(
        self, query: str, tenant_id: str, top_k: int
    ) -> list[RetrievalResult]:
        def _run() -> list[RetrievalResult]:
            ranked = self._bm25.search(tenant_id, query, top_k)
            out: list[RetrievalResult] = []
            for doc_id, sc in ranked:
                text = self._bm25.get_text(tenant_id, doc_id)
                out.append(
                    RetrievalResult(
                        id=doc_id,
                        content=text,
                        score=float(sc),
                        metadata={},
                        source="keyword",
                    )
                )
            return out

        return await asyncio.to_thread(_run)
