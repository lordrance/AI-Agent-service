"""Epic 6：Pinecone 向量库适配器（mock SDK）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.infrastructure.vectordb.base import VectorRecord
from app.infrastructure.vectordb.factory import build_vector_store
from app.infrastructure.vectordb.pinecone_store import PineconeVectorStore


@pytest.mark.asyncio
async def test_pinecone_upsert_search_delete_mocked():
    mock_index = MagicMock()
    mock_match = MagicMock()
    mock_match.id = "c1"
    mock_match.score = 0.9
    mock_match.metadata = {"content": "hello", "document_id": "d1"}
    mock_resp = MagicMock()
    mock_resp.matches = [mock_match]
    mock_index.query.return_value = mock_resp

    store = PineconeVectorStore(
        api_key="test-key",
        index_name="test-index",
    )
    store._index = mock_index  # noqa: SLF001

    rec = VectorRecord(
        id="c1",
        content="hello",
        embedding=[0.1] * 8,
        document_id="d1",
    )
    ids = await store.upsert([rec], namespace="tenant-a")
    assert ids == ["c1"]
    mock_index.upsert.assert_called_once()

    hits = await store.search([0.1] * 8, top_k=3, namespace="tenant-a")
    assert len(hits) == 1
    assert hits[0].content == "hello"

    await store.delete(["c1"], namespace="tenant-a")
    mock_index.delete.assert_called_once_with(ids=["c1"], namespace="tenant-a")


def test_factory_pinecone_requires_key(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE", "pinecone")
    monkeypatch.setenv("PINECONE_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ValueError, match="PINECONE_API_KEY"):
        build_vector_store()
    get_settings.cache_clear()
