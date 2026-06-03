"""将内存 Tracer 的 TraceRecord 导出到 Langfuse。

设计：默认关闭（未配置则为安全 no-op）；任何 SDK 版本差异或网络错误都被吞掉并降级为日志，
不会向调用方抛出异常，从而不影响主链路。内存 Tracer 仍作为本地调试用途保留。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from app.config import get_settings

if TYPE_CHECKING:
    from app.infrastructure.trace.tracer import TraceRecord


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
        trace = client.trace(id=trace_id, name="agent")
        for span in record.spans:
            duration_s = None
            if span.end_time is not None:
                duration_s = span.end_time - span.start_time
            trace.span(
                name=span.operation,
                metadata={
                    "span_id": span.span_id,
                    "parent_span_id": span.parent_span_id,
                    "result": span.result,
                    "error": span.error,
                    "duration_s": duration_s,
                },
            )
        client.flush()
        logger.debug(
            "已导出 trace 到 Langfuse trace_id={} spans={}",
            trace_id,
            len(record.spans),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("导出 Langfuse 失败（已忽略）trace_id={}: {}", trace_id, exc)
