"""向量库端口抽象（VectorStore），便于 pgvector / Pinecone 等实现互换。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorRecord:
    """待写入向量库的一条记录。"""

    id: str
    content: str
    embedding: list[float]
    document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorHit:
    """向量检索命中（score 越大越相关）。"""

    id: str
    content: str
    score: float
    document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """向量库统一接口。"""

    @abstractmethod
    async def upsert(
        self,
        records: list[VectorRecord],
        *,
        namespace: str | None = None,
    ) -> list[str]:
        """插入或更新一批向量，返回写入的 id 列表。

        ``namespace``：Pinecone 用 namespace；pgvector 写入 metadata.tenant_id 并过滤。
        """

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        *,
        namespace: str | None = None,
    ) -> list[VectorHit]:
        """按向量相似度检索 top_k。"""

    @abstractmethod
    async def delete(self, ids: list[str], *, namespace: str | None = None) -> None:
        """按 id 删除。"""

    async def close(self) -> None:
        """释放底层资源（默认无操作）。"""
        return None
