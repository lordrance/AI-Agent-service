# -*- coding: utf-8 -*-
"""对话 API：非流式与流式输出。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from app.api.context import build_thread_id, set_session_id, set_trace_id
from app.config import get_settings
from app.core.guardrails.pipeline import guard_input_text, guard_output_text
from app.core.intent.recognizer import IntentRecognizer
from app.core.langgraph.graph import append_chat_messages, run_chat
from app.core.langgraph.model import _to_openai_messages
from app.infrastructure.llm.factory import build_model_router
from app.infrastructure.llm.model_router import AllModelsUnavailableError
from app.infrastructure.trace.langfuse_exporter import export_trace
from app.infrastructure.trace.tracer import Tracer
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

_tracer = Tracer()
_intent = IntentRecognizer()


def _to_lc_messages(request: ChatRequest) -> list[BaseMessage]:
    """把 API 消息转换为 LangChain 消息类型。"""
    out: list[BaseMessage] = []
    for m in request.messages:
        if m.role == "assistant":
            out.append(AIMessage(content=m.content))
        elif m.role == "system":
            out.append(SystemMessage(content=m.content))
        else:
            out.append(HumanMessage(content=m.content))
    return out


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """非流式对话：经意图识别与链路追踪，通过 LangGraph 对话图（带检查点）作答。"""
    graph = getattr(http_request.app.state, "chat_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，对话图不可用")

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    set_session_id(request.conversation_id)
    span = _tracer.start_trace(trace_id, "chat")

    settings = get_settings()
    try:
        sanitized_messages = list(request.messages)
        if settings.guardrails_enabled:
            for msg in sanitized_messages:
                if msg.role == "user":
                    msg.content = guard_input_text(
                        msg.content,
                        tracer=_tracer,
                        trace_id=trace_id,
                        parent_span=span,
                    )

        user_text = sanitized_messages[-1].content if sanitized_messages else ""
        intent = await _intent.recognize(user_text)
        clarify = await _intent.clarify(user_text, intent)
        logger.info(
            "意图 intent={} conf={} sub={}",
            intent.intent,
            intent.confidence,
            intent.sub_intent,
        )

        req_for_lc = request.model_copy(update={"messages": sanitized_messages})
        lc_messages = _to_lc_messages(req_for_lc)
        if clarify and intent.confidence < _intent.confidence_threshold:
            lc_messages.append(SystemMessage(content=f"（系统提示：{clarify}）"))

        thread_id = build_thread_id(request.conversation_id or str(uuid.uuid4()))
        content = await run_chat(graph, thread_id, lc_messages)

        if settings.guardrails_enabled:
            content = guard_output_text(
                content,
                tracer=_tracer,
                trace_id=trace_id,
                parent_span=span,
            )

        _tracer.end_span(span, result={"thread_id": thread_id})

        response = ChatResponse(
            id=str(uuid.uuid4()),
            model=request.model or settings.openai_model,
            content=content,
            trace_id=trace_id,
            usage=None,
        )
        export_trace(trace_id, _tracer.get_trace(trace_id))
        return response
    except HTTPException:
        raise
    except AllModelsUnavailableError as exc:
        logger.warning("chat 模型不可用: {}", exc)
        _tracer.end_span(span, error=str(exc))
        export_trace(trace_id, _tracer.get_trace(trace_id))
        raise HTTPException(status_code=503, detail="对话模型暂不可用，请稍后重试") from exc
    except Exception as exc:
        logger.exception("chat 失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        export_trace(trace_id, _tracer.get_trace(trace_id))
        raise HTTPException(status_code=500, detail=f"对话失败: {exc!s}") from exc


async def _stream_generator(
    request: ChatRequest,
    http_request: Request,
    trace_id: str,
    span,
) -> AsyncIterator[bytes]:
    """SSE：与 /chat 一致的护栏、thread_id；流结束后写入检查点。"""
    settings = get_settings()
    graph = getattr(http_request.app.state, "chat_graph", None)

    sanitized = list(request.messages)
    if settings.guardrails_enabled:
        for msg in sanitized:
            if msg.role == "user":
                msg.content = guard_input_text(
                    msg.content,
                    tracer=_tracer,
                    trace_id=trace_id,
                    parent_span=span,
                )

    user_text = sanitized[-1].content if sanitized else ""
    intent = await _intent.recognize(user_text)
    clarify = await _intent.clarify(user_text, intent)

    req_for_lc = request.model_copy(update={"messages": sanitized})
    lc_messages = _to_lc_messages(req_for_lc)
    if clarify and intent.confidence < _intent.confidence_threshold:
        lc_messages.append(SystemMessage(content=f"（系统提示：{clarify}）"))

    thread_id = build_thread_id(request.conversation_id or str(uuid.uuid4()))
    model_router = build_model_router()

    if model_router is None:
        err_line = json.dumps({"error": "未配置 API Key"}, ensure_ascii=False)
        yield b"data: " + err_line.encode() + b"\n\n"
        return

    accumulated = ""
    max_buf = settings.chat_stream_buffer_max_chars

    try:
        async for delta in model_router.chat_stream(
            _to_openai_messages(lc_messages),
            model_preference=request.model or settings.openai_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            accumulated += delta
            if len(accumulated) > max_buf:
                accumulated = accumulated[:max_buf]
            event = {"content": delta, "trace_id": trace_id}
            yield b"data: " + json.dumps(event, ensure_ascii=False).encode() + b"\n\n"

        if settings.guardrails_enabled and accumulated:
            accumulated = guard_output_text(
                accumulated,
                tracer=_tracer,
                trace_id=trace_id,
                parent_span=span,
            )

        if graph is not None and lc_messages:
            await append_chat_messages(
                graph,
                thread_id,
                [*lc_messages, AIMessage(content=accumulated)],
            )

        _tracer.end_span(span, result={"thread_id": thread_id, "mode": "stream"})
        yield (
            b"data: "
            + json.dumps(
                {"done": True, "trace_id": trace_id},
                ensure_ascii=False,
            ).encode()
            + b"\n\n"
        )
    except Exception as exc:
        logger.exception("chat_stream 失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        yield b"data: " + json.dumps({"error": str(exc)}, ensure_ascii=False).encode() + b"\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """流式输出（SSE）：护栏 + 检查点持久化与非流式对齐。"""
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    set_session_id(request.conversation_id)
    span = _tracer.start_trace(trace_id, "chat_stream")

    return StreamingResponse(
        _stream_generator(request, http_request, trace_id, span),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-Id": trace_id,
        },
    )
