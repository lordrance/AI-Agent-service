# -*- coding: utf-8 -*-
"""Agent API：ReAct 工具调用，带递归与超时上限。"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.config import get_settings
from app.core.agent.react_agent import ReActAgent
from app.core.tools.builtin import CalculatorTool, WebSearchTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter
from app.models.schemas import AgentRequest, AgentResponse

router = APIRouter(tags=["agent"])


class _ReactLLM:
    """把 ModelRouter 适配为 ReActAgent 期望的 `acomplete(messages) -> str`。"""

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router

    async def acomplete(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
        resp = await self._router.chat(list(messages), **kwargs)
        return resp.content


def _build_registry() -> ToolRegistry:
    """注册无需外部凭据的内置工具。"""
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(WebSearchTool())
    return reg


def _build_llm() -> _ReactLLM:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，Agent 不可用")
    model_router = ModelRouter(
        [
            ModelConfig(
                model_id=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base or None,
            )
        ]
    )
    return _ReactLLM(model_router)


@router.post("/agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest) -> AgentResponse:
    """以 ReAct 方式执行工具调用，受最大步数与总超时约束。"""
    settings = get_settings()
    llm = _build_llm()
    registry = _build_registry()
    max_steps = request.max_steps or settings.agent_max_steps
    session_id = request.session_id or str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    agent = ReActAgent(
        llm=llm,
        tools=registry,
        memory=None,
        max_steps=max_steps,
        session_id=session_id,
    )
    ctx = {"session_id": session_id, "tool_names": registry.list_tool_names()}

    try:
        result = await asyncio.wait_for(
            agent.run(request.input, ctx),
            timeout=settings.agent_timeout_seconds,
        )
    except TimeoutError as exc:
        logger.warning("Agent 运行超时 session={}", session_id)
        raise HTTPException(status_code=504, detail="Agent 运行超时") from exc
    except Exception as exc:
        logger.exception("Agent 运行失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"Agent 运行失败: {exc!s}") from exc

    return AgentResponse(
        success=result.success,
        answer=result.final_answer,
        steps=len(result.steps),
        error=result.error,
        trace_id=trace_id,
    )
