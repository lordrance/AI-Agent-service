"""从 Postgres 加载租户文档分块到 BM25 索引。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.bm25_registry import TenantBm25Registry
from app.infrastructure.database.models import Document, DocumentChunk


async def ensure_tenant_bm25(
    session: AsyncSession,
    registry: TenantBm25Registry,
    tenant_id: str,
) -> None:
    """确保租户 BM25 索引与数据库一致；陈旧（计数不符）时从数据库重建。

    BM25 索引是进程内状态：多 worker 部署下，文档上传只更新处理该请求的 worker，
    其它 worker 的内存索引会落后。这里先用一次轻量 ``count(*)`` 与内存条数比对，
    不一致才全量重载，从而让任意 worker 都能拉齐最新语料（含新增与删除）。
    """
    count_stmt = (
        select(func.count())
        .select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.tenant_id == tenant_id)
    )
    db_count = int((await session.execute(count_stmt)).scalar_one() or 0)

    # 计数一致即视为同步（绝大多数查询走这条快路，仅一次 count 查询）
    if registry.is_synced(tenant_id, db_count):
        return
    # 数据库已无该租户分块：清空可能残留的内存索引
    if db_count == 0:
        registry.replace_tenant_corpus(tenant_id, {})
        return

    stmt = (
        select(DocumentChunk.id, DocumentChunk.content)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    rows = result.all()
    id_to_text = {str(rid): str(content) for rid, content in rows}
    registry.replace_tenant_corpus(tenant_id, id_to_text)
