# -*- coding: utf-8 -*-
"""结构化日志：绑定 trace / tenant / request 上下文。"""

from __future__ import annotations

import sys

from loguru import logger

from app.api.context import get_request_id, get_tenant, get_trace_id
from app.config import get_settings


def _patch_record(record: dict) -> None:
    """为每条日志注入可观测性上下文字段。"""
    extra = record["extra"]
    tenant = get_tenant()
    extra.setdefault("tenant_id", tenant.tenant_id if tenant else "-")
    extra.setdefault("request_id", get_request_id() or "-")
    extra.setdefault("trace_id", get_trace_id() or "-")
    extra.setdefault("session_id", extra.get("session_id", "-"))


def configure_logging() -> None:
    """配置 loguru（幂等：重复调用先移除已有 handler）。"""
    settings = get_settings()
    logger.remove()
    logger.configure(patcher=_patch_record)
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "tenant={extra[tenant_id]} req={extra[request_id]} trace={extra[trace_id]} | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
    )
