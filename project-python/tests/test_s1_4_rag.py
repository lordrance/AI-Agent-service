"""S1.4 验证：RAG 检索排序 + 带引用生成（生成用假 LLM，检索用真实 pgvector）。"""

from __future__ import annotations

import uuid

import pytest

from app.core.rag.generator import RAGGenerator
from app.core.rag.service import RagService
from app.infrastructure.embeddings.hashing import HashingEmbedder
from app.infrastructure.vectordb.base import VectorRecord
from app.infrastructure.vectordb.factory import build_vector_store


class _FakeCitingLLM:
    """假 LLM：基于上下文产出带 [1] 引用的答案。"""

    async def ainvoke(self, messages, **_):
        class _R:
            content = "根据资料，向量检索用于 RAG 问答 [1]。"

        return _R()


@pytest.mark.asyncio
async def test_rag_retrieve_and_generate(require_db):
    store = build_vector_store()
    emb = HashingEmbedder(dim=1536)
    prefix = f"r_{uuid.uuid4().hex[:8]}_"
    texts = {
        f"{prefix}rag": "向量检索与 RAG 知识问答是核心能力",
        f"{prefix}cb": "熔断器在下游失败时快速失败",
        f"{prefix}mem": "短期记忆滑动窗口压缩上下文",
    }
    records = [
        VectorRecord(id=i, content=t, embedding=emb.embed_query(t), document_id="docR")
        for i, t in texts.items()
    ]

    try:
        await store.upsert(records)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pgvector 不可用：{exc}")

    try:
        # 仅检索（无生成器）：RAG 文档应排第一
        svc_no_gen = RagService(vector_store=store, embedder=emb, generator=None)
        contexts = await svc_no_gen.retrieve("RAG 检索问答", top_k=3)
        assert contexts and contexts[0].id == f"{prefix}rag"
        assert contexts[0].metadata.get("document_id") == "docR"

        # 带生成器：返回答案与解析出的引用
        gen = RAGGenerator(llm=_FakeCitingLLM(), model_name="fake")
        svc = RagService(vector_store=store, embedder=emb, generator=gen)
        resp = await svc.answer("RAG 检索问答", top_k=3)
        assert "[1]" in resp.answer
        assert len(resp.citations) == 1
        assert resp.citations[0].index == 1
        assert resp.raw_contexts
    finally:
        await store.delete(list(texts.keys()))
        await store.close()
