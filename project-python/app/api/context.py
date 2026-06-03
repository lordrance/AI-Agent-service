# -*- coding: utf-8 -*-
"""请求级租户上下文（contextvars），供鉴权、限流、日志与 thread_id 隔离。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

_tenant_ctx: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


@dataclass(frozen=True)
class TenantContext:
    """已认证租户信息。"""

    tenant_id: str
    auth_method: str  # api_key | jwt | none
    subject: str | None = None  # JWT sub 或 API key 标识


def set_tenant(ctx: TenantContext | None) -> None:
    _tenant_ctx.set(ctx)


def get_tenant() -> TenantContext | None:
    return _tenant_ctx.get()


def require_tenant_id() -> str:
    """返回当前租户 ID；无上下文时回退 anonymous。"""
    ctx = get_tenant()
    return ctx.tenant_id if ctx else "anonymous"


def set_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def build_thread_id(conversation_or_session: str | None, *, prefix: str = "") -> str:
    """多租户 LangGraph thread_id：tenant:session。"""
    tenant = require_tenant_id()
    sid = conversation_or_session or "default"
    base = f"{tenant}:{sid}"
    return f"{prefix}{base}" if prefix else base
