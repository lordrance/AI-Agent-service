# -*- coding: utf-8 -*-
"""可选 Langfuse 导出：未启用时为空操作。"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.infrastructure.trace.tracer import TraceRecord


def export_trace(trace_id: str, trace_record: TraceRecord | None) -> None:
    """将内存 Trace 导出到 Langfuse（LANGFUSE_ENABLED=true 且已配置密钥时）。"""
    if trace_record is None:
        return
    if os.getenv("LANGFUSE_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        logger.debug("Langfuse 已启用但未配置密钥，跳过 trace_id={}", trace_id)
        return

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.debug("未安装 langfuse 包，跳过 trace 导出")
        return

    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    trace = client.trace(id=trace_id)
    for span in trace_record.spans:
        trace.span(
            id=span.span_id,
            name=span.operation,
            parent_observation_id=span.parent_span_id,
            metadata=span.result,
            level="ERROR" if span.error else "DEFAULT",
        )
    client.flush()
    logger.debug("已导出 trace_id={} 到 Langfuse", trace_id)
