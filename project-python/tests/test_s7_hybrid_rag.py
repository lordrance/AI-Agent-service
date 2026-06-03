"""Epic 7：HybridRetriever 与 RagService 混合检索。"""

from __future__ import annotations

import pytest

from app.core.rag.bm25_registry import TenantBm25Registry
from app.core.rag.hybrid_retriever import HybridRetriever
from app.core.rag.service import RagService
from app.infrastructure.embeddings.hashing import HashingEmbedder
from app.infrastructure.vectordb.base import VectorHit, VectorRecord


class _MemVectorStore:
    def __init__(self) -> None:
        self._data: dict[str, list[VectorRecord]] = {}

    async def upsert(self, records, *, namespace=None):
        ns = namespace or "default"
        self._data.setdefault(ns, []).extend(records)
        return [r.id for r in records]

    async def search(self, query_embedding, top_k=10, *, namespace=None):
        ns = namespace or "default"
        recs = self._data.get(ns, [])[:top_k]
        return [
            VectorHit(id=r.id, content=r.content, score=1.0, document_id=r.document_id)
            for r in recs
        ]

    async def delete(self, ids, *, namespace=None):
        ns = namespace or "default"
        self._data[ns] = [r for r in self._data.get(ns, []) if r.id not in ids]


@pytest.mark.asyncio
async def test_hybrid_retriever_rrf():
    store = _MemVectorStore()
    emb = HashingEmbedder(dim=32)
    reg = TenantBm25Registry(max_docs_per_tenant=100)
    reg.add_chunks("t1", {"k1": "关键词 RAG 检索说明", "k2": "无关文本"})
    await store.upsert(
        [
            VectorRecord(
                id="v1",
                content="向量 RAG 文档",
                embedding=emb.embed_query("RAG"),
                document_id="d1",
            )
        ],
        namespace="t1",
    )
    hybrid = HybridRetriever(store, emb, reg)
    results = await hybrid.retrieve("RAG 检索", "t1", top_k=3)
    assert results
    ids = {r.id for r in results}
    assert "v1" in ids or "k1" in ids


@pytest.mark.asyncio
async def test_rag_service_with_hybrid():
    store = _MemVectorStore()
    emb = HashingEmbedder(dim=32)
    reg = TenantBm25Registry()
    reg.add_chunks("anon", {"x1": "企业级 Agent 后端 API"})
    await store.upsert(
        [
            VectorRecord(
                id="x1",
                content="企业级 Agent 后端 API",
                embedding=emb.embed_query("Agent"),
                document_id="doc",
            )
        ],
        namespace="anonymous",
    )
    hybrid = HybridRetriever(store, emb, reg)
    svc = RagService(
        vector_store=store,
        embedder=emb,
        hybrid=hybrid,
        tenant_id="anonymous",
    )
    ctx = await svc.retrieve("Agent API", top_k=2)
    assert ctx
    assert any("Agent" in c.content for c in ctx)
