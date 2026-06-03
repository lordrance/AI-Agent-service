# -*- coding: utf-8 -*-
"""RAG 问答 API：检索 → 可选重排 → 生成（带引用）。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import require_tenant_id, set_trace_id
from app.config import get_settings
from app.core.guardrails.pipeline import guard_input_text, guard_output_text
from app.core.rag.bm25_registry import TenantBm25Registry
from app.core.rag.corpus_loader import ensure_tenant_bm25
from app.core.rag.generator import RAGGenerator
from app.core.rag.hybrid_retriever import HybridRetriever
from app.core.rag.reranker import Reranker
from app.core.rag.service import RagService
from app.infrastructure.database.session import get_async_session
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.llm.factory import build_model_router
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.trace.tracer import Tracer
from app.infrastructure.vectordb.base import VectorStore
from app.models.schemas import RagQueryRequest, RAGResponse

router = APIRouter(tags=["rag"])
_tracer = Tracer()


def get_vector_store(request: Request) -> VectorStore:
    """从应用状态获取向量库单例。"""
    return request.app.state.vector_store


def get_bm25_registry(request: Request) -> TenantBm25Registry:
    return request.app.state.bm25_registry


class _RouterLLM:
    """把 ModelRouter 适配为 RAGGenerator 期望的 `ainvoke(messages)`。"""

    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    async def ainvoke(self, messages: Any, **_: Any) -> Any:
        return await self._router.chat(messages)


def _build_generator() -> RAGGenerator | None:
    """有 API Key 时构造生成器；否则返回 None（仅检索）。"""
    settings = get_settings()
    router = build_model_router()
    if router is None:
        return None
    return RAGGenerator(llm=_RouterLLM(router), model_name=settings.openai_model)


def _build_reranker() -> Reranker | None:
    settings = get_settings()
    if not settings.rerank_enabled:
        return None
    return Reranker(model_name=settings.reranker_model)


@router.post("/rag/query", response_model=RAGResponse)
async def rag_query(
    http_request: Request,
    request: RagQueryRequest,
    vector_store: VectorStore = Depends(get_vector_store),
    bm25_registry: TenantBm25Registry = Depends(get_bm25_registry),
    session: AsyncSession = Depends(get_async_session),
) -> RAGResponse:
    """检索并生成带引用的答案；未配置模型时仅返回检索上下文。"""
    settings = get_settings()
    top_k = request.top_k or settings.rag_top_k
    tenant_id = require_tenant_id()
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    span = _tracer.start_trace(trace_id, "rag_query")

    query = request.query
    if settings.guardrails_enabled:
        query = guard_input_text(
            query,
            tracer=_tracer,
            trace_id=trace_id,
            parent_span=span,
        )

    hybrid = None
    if settings.rag_hybrid_enabled:
        await ensure_tenant_bm25(session, bm25_registry, tenant_id)
        hybrid = HybridRetriever(vector_store, get_embedder(), bm25_registry)

    service = RagService(
        vector_store=vector_store,
        embedder=get_embedder(),
        generator=_build_generator(),
        reranker=_build_reranker(),
        rerank_top_k=settings.rag_top_k,
        hybrid=hybrid,
        tenant_id=tenant_id,
    )
    try:
        response = await service.answer(query, top_k=top_k)
        if settings.guardrails_enabled and response.answer:
            safe_answer = guard_output_text(
                response.answer,
                tracer=_tracer,
                trace_id=trace_id,
                parent_span=span,
            )
            response = response.model_copy(update={"answer": safe_answer})
        _tracer.end_span(span, result={"top_k": top_k})
        return response
    except HTTPException:
        _tracer.end_span(span, error="guardrail")
        raise
    except Exception as exc:
        logger.exception("RAG 查询失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        raise HTTPException(status_code=500, detail=f"RAG 查询失败: {exc!s}") from exc
