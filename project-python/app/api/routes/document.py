# -*- coding: utf-8 -*-
"""文档管理 API：上传、列表、删除。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import require_tenant_id
from app.etl import ETLPipeline
from app.infrastructure.database.models import Document, DocumentChunk
from app.infrastructure.database.session import get_async_session
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.vectordb.base import VectorRecord, VectorStore
from app.models.schemas import DocumentInfo, DocumentUploadResponse

router = APIRouter(tags=["documents"])


def get_vector_store(request: Request) -> VectorStore:
    """从应用状态获取向量库单例（在 lifespan 中创建）。"""
    return request.app.state.vector_store


def get_bm25_registry(request: Request):
    return request.app.state.bm25_registry


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="上传的文件"),
    session: AsyncSession = Depends(get_async_session),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentUploadResponse:
    """上传文档：ETL 分块 → 嵌入并写入向量库 → 落库元数据与 vector_id。"""
    tenant_id = require_tenant_id()
    upload_root = Path("uploads")
    upload_root.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    safe_name = file.filename or "unnamed"
    dest = upload_root / f"{doc_id}_{safe_name}"

    try:
        raw = await file.read()
        await asyncio.to_thread(dest.write_bytes, raw)
    except Exception as exc:
        logger.exception("保存上传文件失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"保存文件失败: {exc!s}") from exc

    pipeline = ETLPipeline()
    try:
        etl = await pipeline.run_bytes(
            raw,
            filename=safe_name,
            mime_type=file.content_type,
        )
    except Exception as exc:
        logger.exception("ETL 失败: {}", exc)
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc!s}") from exc

    chunk_ids = [str(uuid.uuid4()) for _ in etl.chunks]

    if etl.chunks:
        try:
            embedder = get_embedder()
            embeddings = await asyncio.to_thread(embedder.embed_documents, etl.chunks)
            records = [
                VectorRecord(
                    id=cid,
                    content=text[:65000],
                    embedding=emb,
                    document_id=doc_id,
                    metadata={"chunk_index": i, "filename": safe_name},
                )
                for i, (cid, text, emb) in enumerate(zip(chunk_ids, etl.chunks, embeddings))
            ]
            await vector_store.upsert(records, namespace=tenant_id)
        except Exception as exc:
            logger.exception("文档向量化/入库失败: {}", exc)
            raise HTTPException(status_code=502, detail=f"向量化失败: {exc!s}") from exc

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename=safe_name,
        mime_type=file.content_type,
        storage_path=str(dest),
        status="ready",
        meta={"chunk_count": len(etl.chunks)},
    )
    session.add(doc)

    for i, (cid, chunk_text) in enumerate(zip(chunk_ids, etl.chunks)):
        chunk = DocumentChunk(
            id=cid,
            document_id=doc_id,
            chunk_index=i,
            content=chunk_text[:65000],
            vector_id=cid,
            meta=None,
        )
        session.add(chunk)

    await session.commit()

    bm25 = get_bm25_registry(request)
    bm25.add_chunks(
        tenant_id,
        {cid: text[:65000] for cid, text in zip(chunk_ids, etl.chunks)},
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=safe_name,
        status="ready",
        chunk_count=len(etl.chunks),
        message="上传、分块并向量化成功",
    )


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
) -> list[DocumentInfo]:
    """列出当前租户已入库文档元数据。"""
    tenant_id = require_tenant_id()
    try:
        result = await session.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            DocumentInfo(
                id=d.id,
                filename=d.filename,
                mime_type=d.mime_type,
                status=d.status,
                created_at=d.created_at.isoformat() if d.created_at else None,
            )
            for d in rows
        ]
    except Exception as exc:
        logger.exception("查询文档列表失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"查询失败: {exc!s}") from exc


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, str]:
    """删除文档：元数据、分块与向量。"""
    tenant_id = require_tenant_id()
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    chunks_result = await session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    chunks = chunks_result.scalars().all()
    vector_ids = [c.vector_id for c in chunks if c.vector_id]

    if vector_ids:
        try:
            await vector_store.delete(vector_ids, namespace=tenant_id)
        except Exception as exc:
            logger.exception("删除向量失败: {}", exc)
            raise HTTPException(status_code=502, detail=f"向量删除失败: {exc!s}") from exc

    await session.delete(doc)
    await session.commit()

    bm25 = get_bm25_registry(request)
    bm25.remove_ids(tenant_id, [c.id for c in chunks])

    return {"status": "deleted", "document_id": document_id}
