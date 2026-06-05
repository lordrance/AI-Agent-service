# -*- coding: utf-8 -*-
"""护栏管道：输入清洗 / 输出检查，并写入 Tracer span。"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.guardrails.safety import (
    GuardrailResult,
    check_output_safety,
    sanitize_user_input,
)
from app.infrastructure.trace.tracer import Tracer, TraceSpan


def _span_result(gr: GuardrailResult) -> dict:
    return {
        "allowed": gr.allowed,
        "reason": gr.reason,
        "sanitized_len": len(gr.sanitized_text or ""),
    }


def guard_input_text(
    text: str,
    *,
    tracer: Tracer,
    trace_id: str,
    parent_span: TraceSpan | None = None,
) -> str:
    """输入护栏：注入拒绝 + PII 脱敏；记录 guardrails.input span。"""
    span = (
        tracer.start_child_span(trace_id, "guardrails.input", parent_span.span_id)
        if parent_span
        else tracer.start_trace(trace_id, "guardrails.input")
    )
    try:
        result = sanitize_user_input(text)
        if not result.allowed:
            tracer.end_span(span, result=_span_result(result), error=result.reason)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"输入未通过护栏: {result.reason}",
            )
        out = result.sanitized_text or text
        tracer.end_span(span, result=_span_result(result))
        return out
    except HTTPException:
        raise
    except Exception as exc:
        tracer.end_span(span, error=str(exc))
        raise


def guard_output_text(
    text: str,
    *,
    tracer: Tracer,
    trace_id: str,
    parent_span: TraceSpan | None = None,
) -> str:
    """输出护栏：敏感片段拦截；记录 guardrails.output span。"""
    span = (
        tracer.start_child_span(trace_id, "guardrails.output", parent_span.span_id)
        if parent_span
        else tracer.start_trace(trace_id, "guardrails.output")
    )
    try:
        result = check_output_safety(text)
        if not result.allowed:
            tracer.end_span(span, result=_span_result(result), error=result.reason)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"输出未通过护栏: {result.reason}",
            )
        out = result.sanitized_text or text
        tracer.end_span(span, result=_span_result(result))
        return out
    except HTTPException:
        raise
    except Exception as exc:
        tracer.end_span(span, error=str(exc))
        raise
