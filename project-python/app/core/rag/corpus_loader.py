"""从 Postgres 加载租户文档分块到 BM25 索引。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.bm25_registry import TenantBm25Registry
from app.infrastructure.database.models import Document, DocumentChunk


async def ensure_tenant_bm25(
    session: AsyncSession,
    registry: TenantBm25Registry,
    tenant_id: str,
) -> None:
    """若租户 BM25 为空，从数据库加载语料。"""
    if registry.has_corpus(tenant_id):
        return
    stmt = (
        select(DocumentChunk.id, DocumentChunk.content)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    rows = result.all()
    if not rows:
        return
    id_to_text = {str(rid): str(content) for rid, content in rows}
    registry.replace_tenant_corpus(tenant_id, id_to_text)
