# -*- coding: utf-8 -*-
"""Prometheus 指标定义与记录辅助。"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest

# HTTP
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时（秒）",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# LLM / Agent
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM 调用次数",
    ["model", "status"],
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM token 用量",
    ["model", "direction"],
)
TOOL_INVOCATIONS = Counter(
    "tool_invocations_total",
    "工具调用次数",
    ["tool", "status"],
)
RAG_RETRIEVALS = Counter(
    "rag_retrievals_total",
    "RAG 检索次数",
    ["status"],
)
RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total",
    "限流命中次数",
    ["endpoint"],
)


def metrics_payload() -> bytes:
    return generate_latest()


def record_llm_call(model_id: str, *, success: bool, usage: dict | None = None) -> None:
    status = "success" if success else "error"
    LLM_REQUESTS.labels(model=model_id, status=status).inc()
    if usage:
        if (v := usage.get("prompt_tokens")) is not None:
            LLM_TOKENS.labels(model=model_id, direction="input").inc(int(v))
        if (v := usage.get("completion_tokens")) is not None:
            LLM_TOKENS.labels(model=model_id, direction="output").inc(int(v))


def record_tool(tool_name: str, *, success: bool) -> None:
    TOOL_INVOCATIONS.labels(
        tool=tool_name,
        status="success" if success else "error",
    ).inc()


def record_rag_retrieval(*, success: bool) -> None:
    RAG_RETRIEVALS.labels(status="success" if success else "error").inc()
