# -*- coding: utf-8 -*-
"""slowapi 限流：按租户 ID 或客户端 IP 计数。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import Response

from app.api.context import get_tenant
from app.config import get_settings


def _rate_limit_key(request: Request) -> str:
    tenant = get_tenant()
    if tenant and tenant.tenant_id not in ("anonymous", "public"):
        return f"tenant:{tenant.tenant_id}"
    return get_remote_address(request)


def _create_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=_rate_limit_key,
        default_limits=[settings.rate_limit_default],
        storage_uri=settings.rate_limit_storage_uri or None,
        enabled=settings.rate_limit_enabled,
    )


limiter = _create_limiter()


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    from app.infrastructure.metrics.prometheus import RATE_LIMIT_HITS

    RATE_LIMIT_HITS.labels(endpoint=request.url.path).inc()
    return _rate_limit_exceeded_handler(request, exc)


def setup_rate_limit(application: FastAPI) -> Limiter:
    """注册 slowapi 中间件与 429 处理。"""
    settings = get_settings()
    limiter.enabled = settings.rate_limit_enabled
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    application.add_middleware(SlowAPIMiddleware)
    return limiter
