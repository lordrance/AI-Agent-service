"""S2.2：httpx + ASGI 集成测试 — 四条主链路与健康检查。"""

from __future__ import annotations

import io
import uuid

import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.fixture
async def api_client():
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_health_liveness(api_client: httpx.AsyncClient):
    r = await api_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(api_client: httpx.AsyncClient, require_db):
    r = await api_client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "up"
    assert body["status"] == "ready"


@pytest.mark.asyncio
async def test_chat_without_api_key_returns_503(api_client: httpx.AsyncClient):
    r = await api_client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": "你好"}],
            "conversation_id": str(uuid.uuid4()),
        },
    )
    # 无 OPENAI_API_KEY 时对话图未启用
    if r.status_code == 503:
        assert "未配置" in r.json().get("detail", "") or "API" in r.json().get("detail", "")
    else:
        # 若环境已配置密钥，应能 200
        assert r.status_code in (200, 503)


@pytest.mark.asyncio
async def test_rag_query_retrieval_only(api_client: httpx.AsyncClient, require_db):
    r = await api_client.post(
        "/api/v1/rag/query",
        json={"query": "熔断器 RAG", "top_k": 3},
    )
    assert r.status_code == 200
    data = r.json()
    assert "raw_contexts" in data
    assert isinstance(data["raw_contexts"], list)


@pytest.mark.asyncio
async def test_agent_without_api_key(api_client: httpx.AsyncClient):
    r = await api_client.post(
        "/api/v1/agent",
        json={"input": "1+1", "session_id": "e2e-agent"},
    )
    assert r.status_code in (200, 503, 504)


@pytest.mark.asyncio
async def test_document_upload_pipeline(api_client: httpx.AsyncClient, require_db):
    content = b"RAG vector retrieval test document. Unique token: " + uuid.uuid4().hex.encode()
    files = {"file": ("sample.txt", io.BytesIO(content), "text/plain")}
    r = await api_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body.get("chunk_count", 0) >= 1
