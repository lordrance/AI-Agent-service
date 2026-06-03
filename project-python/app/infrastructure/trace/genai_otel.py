# -*- coding: utf-8 -*-
"""OpenTelemetry GenAI 语义约定埋点（可选启用）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import get_settings

# GenAI 语义约定（incubating）常用属性名
ATTR_SYSTEM = "gen_ai.system"
ATTR_OPERATION = "gen_ai.operation.name"
ATTR_REQUEST_MODEL = "gen_ai.request.model"
ATTR_USAGE_INPUT = "gen_ai.usage.input_tokens"
ATTR_USAGE_OUTPUT = "gen_ai.usage.output_tokens"
ATTR_FINISH_REASONS = "gen_ai.response.finish_reasons"
ATTR_TOOL_NAME = "gen_ai.tool.name"
ATTR_RETRIEVAL_HIT_COUNT = "gen_ai.retrieval.hit_count"


def _tracer():
    from opentelemetry import trace

    settings = get_settings()
    return trace.get_tracer(settings.otel_service_name or "enterprise-ai-agent")


@contextmanager
def genai_span(
    operation: str,
    *,
    system: str = "openai",
    model: str | None = None,
    tool_name: str | None = None,
) -> Iterator[Any]:
    """创建 GenAI 语义 span；未启用 OTel 时为 no-op。"""
    if not get_settings().otel_enabled:
        yield None
        return

    attrs: dict[str, str | int] = {
        ATTR_SYSTEM: system,
        ATTR_OPERATION: operation,
    }
    if model:
        attrs[ATTR_REQUEST_MODEL] = model
    if tool_name:
        attrs[ATTR_TOOL_NAME] = tool_name

    with _tracer().start_as_current_span(operation, attributes=attrs) as span:
        yield span


def record_llm_usage(
    span: Any,
    *,
    model_id: str,
    usage: dict[str, Any] | None,
    finish_reason: str | None = None,
) -> None:
    """在 span 上记录 token 用量与 finish_reason。"""
    if span is None:
        return
    span.set_attribute(ATTR_REQUEST_MODEL, model_id)
    if usage:
        if (inp := usage.get("prompt_tokens")) is not None:
            span.set_attribute(ATTR_USAGE_INPUT, int(inp))
        if (out := usage.get("completion_tokens")) is not None:
            span.set_attribute(ATTR_USAGE_OUTPUT, int(out))
    if finish_reason:
        span.set_attribute(ATTR_FINISH_REASONS, [finish_reason])


def record_retrieval(span: Any, *, hit_count: int, model: str | None = None) -> None:
    if span is None:
        return
    span.set_attribute(ATTR_RETRIEVAL_HIT_COUNT, hit_count)
    if model:
        span.set_attribute(ATTR_REQUEST_MODEL, model)
