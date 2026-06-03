# -*- coding: utf-8 -*-
"""API Key 与 JWT 鉴权解析。"""

from __future__ import annotations

import secrets
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from loguru import logger

from app.api.context import TenantContext
from app.config import Settings


def parse_api_key_map(raw: str) -> dict[str, str]:
    """
    解析 API_KEYS 配置。

    格式（逗号分隔）：
    - ``tenant_id:secret``
    - 或仅 ``secret``（租户默认为 ``default``）
    """
    mapping: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            tenant, key = part.split(":", 1)
            mapping[key.strip()] = tenant.strip() or "default"
        else:
            mapping[part] = "default"
    return mapping


def authenticate_request(request: Request, settings: Settings) -> TenantContext:
    """
    从 X-API-Key 或 Authorization Bearer JWT 解析租户。

    :raises HTTPException: 401 未提供或无效凭据
    """
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        key_map = parse_api_key_map(settings.api_keys)
        tenant = key_map.get(api_key)
        if tenant is None:
            logger.warning("无效 API Key（租户未知）")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 API Key",
            )
        return TenantContext(tenant_id=tenant, auth_method="api_key", subject=api_key[:8])

    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if not settings.jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="服务未配置 JWT 密钥",
            )
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                audience=settings.jwt_audience or None,
                options={"verify_aud": bool(settings.jwt_audience)},
            )
        except jwt.PyJWTError as exc:
            logger.warning("JWT 校验失败: {}", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的 JWT",
            ) from exc

        tenant_id = str(payload.get("tenant_id") or payload.get("tid") or payload.get("sub") or "")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 缺少 tenant_id/sub",
            )
        return TenantContext(
            tenant_id=tenant_id,
            auth_method="jwt",
            subject=str(payload.get("sub")) if payload.get("sub") else None,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需要 X-API-Key 或 Authorization Bearer JWT",
    )


def auth_is_configured(settings: Settings) -> bool:
    """是否已配置任一鉴权凭据。"""
    return bool(settings.api_keys.strip() or settings.jwt_secret.strip())


def constant_time_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())
