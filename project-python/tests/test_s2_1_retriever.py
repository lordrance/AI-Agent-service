"""S2.1：BM25 关键词检索与 RRF 融合。"""

from __future__ import annotations

import pytest

from app.core.rag.retriever import MultiRetriever, _BM25Index, _tokenize
from app.models.schemas import RetrievalResult


def test_tokenize_splits_cjk_and_latin():
    tokens = _tokenize("RAG 向量检索 test")
    assert "rag" in tokens
    assert "向量检索" in tokens
    assert "test" in tokens


def test_bm25_ranks_relevant_doc_first():
    idx = _BM25Index()
    idx.add_document("a", "熔断器保护下游服务")
    idx.add_document("b", "向量检索用于 RAG 问答")
    ranked = idx.search("RAG 检索", top_k=2)
    assert ranked[0][0] == "b"


@pytest.mark.asyncio
async def test_hybrid_rrf_fuses_vector_and_keyword():
    class _FakeEmbed:
        def embed_query(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3]

    class _Hit:
        def __init__(self, entity: dict, distance: float = 0.1) -> None:
            self.entity = entity
            self.distance = distance
            self.id = entity.get("id")

    class _FakeMilvus:
        def search(self, data, anns_field, param, limit, output_fields=None, **kwargs):
            return [
                [
                    _Hit({"id": "v1", "text": "向量 RAG 文档"}, 0.2),
                    _Hit({"id": "v2", "text": "无关内容"}, 0.9),
                ]
            ]

    retriever = MultiRetriever(_FakeMilvus(), _FakeEmbed())
    retriever.register_keyword_documents(
        {
            "v1": "向量 RAG 文档",
            "k1": "关键词 RAG 检索说明",
        }
    )

    results = await retriever.hybrid_search("RAG 检索", top_k=3)
    assert results
    ids = {r.id for r in results}
    assert "v1" in ids or "k1" in ids
    assert all(r.source == "hybrid" for r in results)


def test_rrf_fuse_merges_rankings():
    retriever = MultiRetriever(milvus_client=None, embedding_model=None)
    list_a = [
        RetrievalResult(id="x", content="a", score=1.0, source="vector"),
        RetrievalResult(id="y", content="b", score=0.5, source="vector"),
    ]
    list_b = [
        RetrievalResult(id="y", content="b", score=2.0, source="keyword"),
        RetrievalResult(id="z", content="c", score=1.0, source="keyword"),
    ]
    merged = retriever._rrf_fuse([list_a, list_b], top_k=2)
    assert len(merged) == 2
    merged_ids = [m.id for m in merged]
    assert "y" in merged_ids
