# -*- coding: utf-8 -*-
"""Agent API：ReAct 工具调用，带递归与超时上限。"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from app.api.context import build_thread_id, require_tenant_id, set_session_id, set_trace_id
from app.config import get_settings
from app.core.agent.react_agent import ReActAgent
from app.core.guardrails.pipeline import guard_input_text, guard_output_text
from app.core.memory.manager import MemoryManager
from app.core.memory.short_term import ShortTermMemory
from app.core.memory.vector_long_term import VectorLongTermMemory
from app.core.tools.builtin import CalculatorTool, WebSearchTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.llm.factory import build_model_router
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.trace.tracer import Tracer
from app.infrastructure.vectordb.base import VectorStore
from app.models.schemas import AgentRequest, AgentResponse

router = APIRouter(tags=["agent"])
_tracer = Tracer()


class _ReactLLM:
    """把 ModelRouter 适配为 ReActAgent 期望的 `acomplete(messages) -> str`。"""

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router

    async def acomplete(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
        resp = await self._router.chat(list(messages), **kwargs)
        return resp.content


def _build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(WebSearchTool())
    return reg


def _build_llm() -> _ReactLLM:
    model_router = build_model_router()
    if model_router is None:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，Agent 不可用")
    return _ReactLLM(model_router)


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


class _NoopCompressLLM:
    async def ainvoke(self, input: Any, **kwargs: Any) -> str:
        return str(input)[:500]


def _build_memory(request: AgentRequest, vector_store: VectorStore) -> MemoryManager | None:
    if not request.use_memory:
        return None
    settings = get_settings()
    tenant_id = require_tenant_id()
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    stm = ShortTermMemory(redis_client, _NoopCompressLLM())
    ltm = VectorLongTermMemory(
        vector_store=vector_store,
        embedder=get_embedder(),
        tenant_id=tenant_id,
    )
    return MemoryManager(short_term=stm, long_term=ltm)


@router.post("/agent", response_model=AgentResponse)
async def run_agent(
    request: AgentRequest,
    http_request: Request,
    vector_store: VectorStore = Depends(get_vector_store),
) -> AgentResponse:
    """以 ReAct 方式执行工具调用，受最大步数与总超时约束。"""
    settings = get_settings()
    llm = _build_llm()
    registry = _build_registry()
    max_steps = request.max_steps or settings.agent_max_steps
    session_id = build_thread_id(request.session_id or str(uuid.uuid4()))
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    set_session_id(request.session_id)
    span = _tracer.start_trace(trace_id, "agent")

    user_input = request.input
    if settings.guardrails_enabled:
        user_input = guard_input_text(
            user_input,
            tracer=_tracer,
            trace_id=trace_id,
            parent_span=span,
        )

    memory = _build_memory(request, vector_store)

    agent = ReActAgent(
        llm=llm,
        tools=registry,
        memory=memory,
        max_steps=max_steps,
        session_id=session_id,
    )
    ctx = {"session_id": session_id, "tool_names": registry.list_tool_names()}

    try:
        result = await asyncio.wait_for(
            agent.run(user_input, ctx),
            timeout=settings.agent_timeout_seconds,
        )
    except TimeoutError as exc:
        logger.warning("Agent 运行超时 session={}", session_id)
        _tracer.end_span(span, error="timeout")
        raise HTTPException(status_code=504, detail="Agent 运行超时") from exc
    except HTTPException:
        _tracer.end_span(span, error="guardrail")
        raise
    except Exception as exc:
        logger.exception("Agent 运行失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Agent 运行失败: {exc!s}") from exc

    answer = result.final_answer
    if settings.guardrails_enabled and answer:
        answer = guard_output_text(
            answer,
            tracer=_tracer,
            trace_id=trace_id,
            parent_span=span,
        )

    _tracer.end_span(span, result={"success": result.success, "steps": len(result.steps)})

    return AgentResponse(
        success=result.success,
        answer=answer,
        steps=len(result.steps),
        error=result.error,
        trace_id=trace_id,
    )
