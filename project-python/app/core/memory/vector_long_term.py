"""长期记忆：基于 VectorStore 端口（Pinecone / pgvector）。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.infrastructure.embeddings.base import Embedder
from app.infrastructure.vectordb.base import VectorRecord, VectorStore
from app.models.schemas import MemoryItem


class VectorLongTermMemory:
    """Agent 长期记忆：向量写入与按 session 召回。"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        *,
        tenant_id: str,
    ) -> None:
        self._vs = vector_store
        self._embedder = embedder
        self._tenant_id = tenant_id

    async def store(self, session_id: str, content: str, metadata: dict[str, Any]) -> str:
        memory_id = str(uuid.uuid4())
        meta = dict(metadata)
        meta["memory_id"] = memory_id
        meta["session_id"] = session_id
        meta["kind"] = "agent_memory"
        vec = await asyncio.to_thread(self._embedder.embed_query, content)
        record = VectorRecord(
            id=memory_id,
            content=content[:65000],
            embedding=vec,
            document_id=None,
            metadata=meta,
        )
        await self._vs.upsert([record], namespace=self._tenant_id)
        return memory_id

    async def recall(self, query: str, session_id: str, top_k: int = 5) -> list[MemoryItem]:
        vec = await asyncio.to_thread(self._embedder.embed_query, query)
        hits = await self._vs.search(vec, top_k=top_k * 3, namespace=self._tenant_id)
        items: list[MemoryItem] = []
        for h in hits:
            meta = h.metadata or {}
            if meta.get("session_id") != session_id:
                continue
            if meta.get("kind") != "agent_memory":
                continue
            items.append(
                MemoryItem(
                    id=h.id,
                    content=h.content,
                    score=h.score,
                    metadata=meta,
                )
            )
            if len(items) >= top_k:
                break
        return items

    async def forget(self, memory_id: str) -> None:
        await self._vs.delete([memory_id], namespace=self._tenant_id)
