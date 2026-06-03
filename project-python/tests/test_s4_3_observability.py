"""S4.3：Prometheus /metrics 与就绪探针扩展。"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.config import get_settings


@pytest.fixture
async def obs_client(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("PROMETHEUS_ENABLED", "true")
    get_settings.cache_clear()

    from app.api.rate_limit import limiter
    from app.main import create_app

    limiter.enabled = False
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_metrics_endpoint(obs_client: httpx.AsyncClient):
    r = await obs_client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


@pytest.mark.asyncio
async def test_health_ready_includes_dependencies(obs_client: httpx.AsyncClient, require_db):
    r = await obs_client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert "database" in body
    assert "redis" in body
    assert "vector_store" in body
