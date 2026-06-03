"""S3.2：安全响应头、CORS、请求体大小限制。"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.config import get_settings


@pytest.fixture
async def api_client(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "1024")
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
async def test_security_headers_on_health(api_client: httpx.AsyncClient):
    r = await api_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Request-Id")


@pytest.mark.asyncio
async def test_cors_preflight(api_client: httpx.AsyncClient):
    r = await api_client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers


@pytest.mark.asyncio
async def test_request_body_too_large(api_client: httpx.AsyncClient):
    body = b'{"query":"' + b"x" * 2030 + b'"}'
    r = await api_client.post(
        "/api/v1/rag/query",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        },
    )
    assert r.status_code == 413
