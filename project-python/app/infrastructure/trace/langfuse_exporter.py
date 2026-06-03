"""将内存 Tracer 的 TraceRecord 导出到 Langfuse。

设计：默认关闭（未配置则为安全 no-op）；任何 SDK 版本差异或网络错误都被吞掉并降级为日志，
不会向调用方抛出异常，从而不影响主链路。内存 Tracer 仍作为本地调试用途保留。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from app.api.context import get_request_id, get_session_id, get_tenant, get_trace_id
from app.config import get_settings

if TYPE_CHECKING:
    from app.infrastructure.trace.tracer import TraceRecord


def _observability_metadata() -> dict[str, Any]:
    """结构化导出：租户 / 请求 / 会话上下文。"""
    tenant = get_tenant()
    meta: dict[str, Any] = {
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "session_id": get_session_id(),
    }
    if tenant:
        meta["tenant_id"] = tenant.tenant_id
        meta["auth_method"] = tenant.auth_method
        if tenant.subject:
            meta["subject"] = tenant.subject
    return {k: v for k, v in meta.items() if v}


def export_trace(trace_id: str, record: TraceRecord | None) -> None:
    """将一次 Trace 的内存记录导出到 Langfuse（可选）。

    - 未启用 Langfuse 或无记录时直接返回；
    - Langfuse 未安装或 SDK 调用失败时仅记录告警，不抛异常。
    """
    settings = get_settings()
    if not getattr(settings, "langfuse_enabled", False):
        return
    if record is None:
        return

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.debug("langfuse 未安装，跳过导出 trace_id={}", trace_id)
        return

    try:
        client = Langfuse(
            public_key=settings.langfuse_public_key or None,
            secret_key=settings.langfuse_secret_key or None,
            host=settings.langfuse_host or None,
        )
        meta = _observability_metadata()
        trace = client.trace(
            id=trace_id,
            name="agent",
            user_id=str(meta.get("tenant_id")) if meta.get("tenant_id") else None,
            session_id=str(meta.get("session_id")) if meta.get("session_id") else None,
            metadata=meta,
        )
        for span in record.spans:
            duration_s = None
            if span.end_time is not None:
                duration_s = span.end_time - span.start_time
            span_meta: dict[str, Any] = {
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "result": span.result,
                "error": span.error,
                "duration_s": duration_s,
                **meta,
            }
            trace.span(
                name=span.operation,
                metadata=span_meta,
            )
        client.flush()
        logger.debug(
            "已导出 trace 到 Langfuse trace_id={} spans={} tenant={}",
            trace_id,
            len(record.spans),
            meta.get("tenant_id"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("导出 Langfuse 失败（已忽略）trace_id={}: {}", trace_id, exc)
