# -*- coding: utf-8 -*-
"""RAG 问答 API：检索 → 可选重排 → 生成（带引用）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from app.config import get_settings
from app.core.rag.generator import RAGGenerator
from app.core.rag.reranker import Reranker
from app.core.rag.service import RagService
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter
from app.infrastructure.vectordb.base import VectorStore
from app.models.schemas import RagQueryRequest, RAGResponse

router = APIRouter(tags=["rag"])


def get_vector_store(request: Request) -> VectorStore:
    """从应用状态获取向量库单例。"""
    return request.app.state.vector_store


class _RouterLLM:
    """把 ModelRouter 适配为 RAGGenerator 期望的 `ainvoke(messages)`。"""

    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    async def ainvoke(self, messages: Any, **_: Any) -> Any:
        return await self._router.chat(messages)


def _build_generator() -> RAGGenerator | None:
    """有 API Key 时构造生成器；否则返回 None（仅检索）。"""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    router = ModelRouter(
        [
            ModelConfig(
                model_id=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base or None,
            )
        ]
    )
    return RAGGenerator(llm=_RouterLLM(router), model_name=settings.openai_model)


def _build_reranker() -> Reranker | None:
    settings = get_settings()
    if not settings.rerank_enabled:
        return None
    return Reranker(model_name=settings.reranker_model)


@router.post("/rag/query", response_model=RAGResponse)
async def rag_query(
    request: RagQueryRequest,
    vector_store: VectorStore = Depends(get_vector_store),
) -> RAGResponse:
    """检索并生成带引用的答案；未配置模型时仅返回检索上下文。"""
    settings = get_settings()
    top_k = request.top_k or settings.rag_top_k

    service = RagService(
        vector_store=vector_store,
        embedder=get_embedder(),
        generator=_build_generator(),
        reranker=_build_reranker(),
        rerank_top_k=settings.rag_top_k,
    )
    try:
        return await service.answer(request.query, top_k=top_k)
    except Exception as exc:
        logger.exception("RAG 查询失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"RAG 查询失败: {exc!s}") from exc
