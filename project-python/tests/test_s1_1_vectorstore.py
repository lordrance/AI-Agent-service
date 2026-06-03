"""S1.1 验证：嵌入工厂 + pgvector VectorStore 写入/检索闭环。

pgvector 用例需要可达的 PostgreSQL（含 vector 扩展与 knowledge_vectors 表）；
若连接失败则跳过（CI 在引入 DB service 后即生效）。
"""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.embeddings.hashing import HashingEmbedder
from app.infrastructure.vectordb.base import VectorRecord
from app.infrastructure.vectordb.factory import build_vector_store


def test_hashing_embedder_deterministic_and_normalized():
    emb = HashingEmbedder(dim=1536)
    v1 = emb.embed_query("企业级 AI Agent 服务")
    v2 = emb.embed_query("企业级 AI Agent 服务")
    assert v1 == v2  # 确定性
    assert len(v1) == 1536
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6  # L2 归一化

    docs = emb.embed_documents(["a", "b"])
    assert len(docs) == 2 and len(docs[0]) == 1536


@pytest.mark.asyncio
async def test_pgvector_roundtrip():
    store = build_vector_store()
    emb = HashingEmbedder(dim=1536)
    prefix = f"t_{uuid.uuid4().hex[:8]}_"

    texts = {
        f"{prefix}rag": "向量检索与 RAG 知识问答",
        f"{prefix}cb": "熔断器保护下游服务",
        f"{prefix}mem": "短期记忆滑动窗口压缩",
    }
    records = [
        VectorRecord(id=rid, content=txt, embedding=emb.embed_query(txt), document_id="doc1")
        for rid, txt in texts.items()
    ]

    try:
        await store.upsert(records)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL/pgvector 不可用，跳过：{exc}")

    try:
        hits = await store.search(emb.embed_query("RAG 检索问答"), top_k=3)
        assert hits, "检索结果不应为空"
        # 与查询最相关的应是 RAG 文档
        assert hits[0].id == f"{prefix}rag"
        assert hits[0].document_id == "doc1"
        # score 越大越相关，应降序
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
    finally:
        await store.delete(list(texts.keys()))
        await store.close()
