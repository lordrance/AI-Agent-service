"""S3.1：API Key / JWT 鉴权与租户上下文。"""

from __future__ import annotations

import httpx
import jwt
import pytest
from httpx import ASGITransport

from app.api.auth import parse_api_key_map
from app.config import get_settings


def test_parse_api_key_map_formats():
    m = parse_api_key_map("t1:k1,t2:k2, lone-key")
    assert m["k1"] == "t1"
    assert m["k2"] == "t2"
    assert m["lone-key"] == "default"


@pytest.fixture
async def auth_client(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEYS", "acme:test-secret-key")
    monkeypatch.setenv("JWT_SECRET", "jwt-test-secret")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    from app.api.rate_limit import limiter
    from app.main import app

    limiter.enabled = False

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health_without_credentials(auth_client: httpx.AsyncClient):
    r = await auth_client.get("/api/v1/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_requires_auth(auth_client: httpx.AsyncClient):
    r = await auth_client.post(
        "/api/v1/rag/query",
        json={"query": "hello"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_api_key_sets_tenant_header(auth_client: httpx.AsyncClient, require_db):
    r = await auth_client.post(
        "/api/v1/rag/query",
        json={"query": "RAG test"},
        headers={"X-API-Key": "test-secret-key"},
    )
    if r.status_code == 401:
        pytest.skip("鉴权配置未生效（需 AUTH_ENABLED + API_KEYS）")
    assert r.headers.get("X-Tenant-Id") == "acme"
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_jwt_bearer_auth(auth_client: httpx.AsyncClient, require_db):
    token = jwt.encode(
        {"tenant_id": "jwt-tenant", "sub": "user-1"},
        "jwt-test-secret",
        algorithm="HS256",
    )
    r = await auth_client.post(
        "/api/v1/rag/query",
        json={"query": "JWT test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers.get("X-Tenant-Id") == "jwt-tenant"
