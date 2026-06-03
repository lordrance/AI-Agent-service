# -*- coding: utf-8 -*-
"""HTTP 中间件：请求 ID、鉴权、安全响应头、请求体大小限制。"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.api.auth import auth_is_configured, authenticate_request
from app.api.context import TenantContext, get_tenant, set_request_id, set_tenant
from app.config import Settings, get_settings


def _is_public_path(path: str) -> bool:
    """健康检查与 OpenAPI 文档无需鉴权。"""
    public_suffixes = (
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
    )
    return any(path.endswith(s) or s + "/" in path for s in public_suffixes)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 request_id，并在启用鉴权时解析租户。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        set_request_id(rid)

        path = request.url.path
        if _is_public_path(path):
            set_tenant(TenantContext(tenant_id="public", auth_method="none"))
            response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            return response

        if settings.auth_enabled:
            if not auth_is_configured(settings):
                logger.error("AUTH_ENABLED=true 但未配置 API_KEYS 或 JWT_SECRET")
                return JSONResponse(
                    status_code=503,
                    content={"detail": "鉴权已启用但服务未配置凭据"},
                )
            try:
                tenant = authenticate_request(request, settings)
            except HTTPException as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                )
            set_tenant(tenant)
            logger.bind(
                tenant_id=tenant.tenant_id,
                auth_method=tenant.auth_method,
                request_id=rid,
            ).debug("鉴权通过 path={}", path)
        else:
            set_tenant(TenantContext(tenant_id="anonymous", auth_method="none"))

        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        tenant = get_tenant()
        if tenant:
            response.headers["X-Tenant-Id"] = tenant.tenant_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """常见安全响应头。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        if get_settings().app_env != "development":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """拒绝超过配置大小的请求体（Content-Length）。"""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            raw_len = request.headers.get("content-length")
            if raw_len:
                try:
                    length = int(raw_len)
                except ValueError:
                    length = 0
                if length > self._max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"请求体超过限制 ({self._max_bytes} 字节)",
                        },
                    )
        return await call_next(request)


def configure_middleware(application: FastAPI, settings: Settings) -> None:
    """按顺序注册中间件（后注册的先执行）。"""
    application.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestContextMiddleware)
