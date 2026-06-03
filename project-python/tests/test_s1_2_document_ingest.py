"""S1.2 验证：文档上传 → ETL 分块 → 嵌入 → 写入 pgvector → 落库 vector_id。"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
from fastapi.testclient import TestClient

from app.config import get_settings
from app.infrastructure.vectordb.pgvector_store import _to_asyncpg_dsn


async def _cleanup(doc_id: str) -> None:
    conn = await asyncpg.connect(_to_asyncpg_dsn(get_settings().database_url))
    try:
        await conn.execute("DELETE FROM knowledge_vectors WHERE document_id=$1", doc_id)
        await conn.execute("DELETE FROM documents WHERE id=$1", doc_id)
    finally:
        await conn.close()


async def _count_vectors(doc_id: str) -> int:
    conn = await asyncpg.connect(_to_asyncpg_dsn(get_settings().database_url))
    try:
        return await conn.fetchval(
            "SELECT count(*) FROM knowledge_vectors WHERE document_id=$1", doc_id
        )
    finally:
        await conn.close()


def test_upload_embeds_and_persists(require_db):
    from app.main import app

    marker = uuid.uuid4().hex
    content = (
        f"标记{marker}。向量检索与 RAG 知识问答是本服务核心能力。\n\n"
        "熔断器在下游连续失败时快速失败，保护系统稳定。\n\n"
        "短期记忆采用滑动窗口与摘要压缩，控制上下文长度。"
    )
    doc_id = None
    try:
        with TestClient(app) as client:
            files = {"file": (f"note_{marker}.txt", content.encode("utf-8"), "text/plain")}
            resp = client.post("/api/v1/documents/upload", files=files)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["status"] == "ready"
            assert data["chunk_count"] >= 1
            doc_id = data["document_id"]

            listed = client.get("/api/v1/documents")
            assert listed.status_code == 200
            assert any(d["id"] == doc_id for d in listed.json())

        # 向量已写入，且数量与分块数一致
        n_vectors = asyncio.run(_count_vectors(doc_id))
        assert n_vectors == data["chunk_count"]
    finally:
        if doc_id:
            asyncio.run(_cleanup(doc_id))
