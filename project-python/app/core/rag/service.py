"""RAG 服务编排：检索（pgvector）→ 可选重排 → 生成（带引用）。

设计为可注入依赖，便于在无 LLM/无 torch 环境下单测检索与装配；
重排默认关闭（需 sentence-transformers），生成在无模型时退化为仅返回检索结果。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.rag.generator import RAGGenerator
from app.core.rag.hybrid_retriever import HybridRetriever
from app.core.rag.reranker import Reranker
from app.infrastructure.embeddings.base import Embedder
from app.infrastructure.metrics.prometheus import record_rag_retrieval
from app.infrastructure.trace.genai_otel import genai_span, record_retrieval
from app.infrastructure.vectordb.base import VectorStore
from app.models.schemas import RAGResponse, RetrievalResult


class RagService:
    """RAG 主链路编排器。"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        generator: RAGGenerator | None = None,
        reranker: Reranker | None = None,
        rerank_top_k: int = 5,
        hybrid: HybridRetriever | None = None,
        tenant_id: str = "anonymous",
    ) -> None:
        self._vs = vector_store
        self._embedder = embedder
        self._generator = generator
        self._reranker = reranker
        self._rerank_top_k = rerank_top_k
        self._hybrid = hybrid
        self._tenant_id = tenant_id

    async def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        """混合或向量检索（可选重排），返回 RetrievalResult 列表。"""
        with genai_span("gen_ai.retrieval") as span:
            try:
                if self._hybrid is not None:
                    results = await self._hybrid.retrieve(query, self._tenant_id, top_k=top_k)
                else:
                    vector = await asyncio.to_thread(self._embedder.embed_query, query)
                    hits = await self._vs.search(vector, top_k=top_k, namespace=self._tenant_id)
                    results = [
                        RetrievalResult(
                            id=h.id,
                            content=h.content,
                            score=h.score,
                            metadata={**h.metadata, "document_id": h.document_id},
                            source="vector",
                        )
                        for h in hits
                    ]
                if self._reranker is not None and results:
                    try:
                        results = await self._reranker.rerank(
                            query, results, top_k=self._rerank_top_k
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("重排失败，回退原始检索顺序: {}", exc)
                record_retrieval(span, hit_count=len(results))
                record_rag_retrieval(success=True)
                return results
            except Exception:
                record_rag_retrieval(success=False)
                raise

    async def answer(
        self,
        query: str,
        top_k: int = 5,
        chat_history: list[Any] | None = None,
    ) -> RAGResponse:
        """检索并生成带引用的答案；无生成器时仅返回检索上下文。"""
        contexts = await self.retrieve(query, top_k=top_k)
        if self._generator is None:
            return RAGResponse(answer="", citations=[], raw_contexts=contexts, model=None)
        return await self._generator.generate(query, contexts, chat_history or [])
