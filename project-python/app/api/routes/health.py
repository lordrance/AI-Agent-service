# -*- coding: utf-8 -*-
"""健康检查：进程存活、依赖就绪与 Prometheus 指标。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import limiter
from app.config import get_settings
from app.infrastructure.database.session import get_async_session
from app.infrastructure.health.probes import check_database, check_redis, check_vector_store
from app.infrastructure.metrics.prometheus import metrics_payload

router = APIRouter(tags=["health"])


@router.get("/health")
@limiter.exempt
async def health(request: Request) -> dict[str, str]:
    """轻量存活探针（不访问外部依赖）。"""
    return {"status": "ok"}


@router.get("/health/ready")
@limiter.exempt
async def health_ready(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """就绪探针：数据库、Redis、向量库（pgvector）。"""
    settings = get_settings()
    db_ok = await check_database(session)
    redis_ok = await check_redis(settings)
    vector_ok = False
    try:
        vector_ok = await check_vector_store(request.app.state.vector_store)
    except Exception as exc:
        logger.warning("向量库状态读取失败: {}", exc)

    checks = {
        "database": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
        "vector_store": "up" if vector_ok else "down",
    }
    all_ok = all(v == "up" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        **checks,
        "app_env": settings.app_env,
    }


@router.get("/metrics")
@limiter.exempt
async def metrics(request: Request) -> Response:
    """Prometheus 指标（无需鉴权）。"""
    settings = get_settings()
    if not settings.prometheus_enabled:
        return Response(status_code=404, content="metrics disabled")
    return Response(
        content=metrics_payload(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
