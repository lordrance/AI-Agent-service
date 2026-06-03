# -*- coding: utf-8 -*-
"""向量数据库封装：VectorStore 端口 + pgvector 实现（Milvus 作为可选实现保留）。"""

from app.infrastructure.vectordb.base import VectorHit, VectorRecord, VectorStore
from app.infrastructure.vectordb.factory import build_vector_store
from app.infrastructure.vectordb.milvus_client import MilvusManager
from app.infrastructure.vectordb.pgvector_store import PgVectorStore
from app.infrastructure.vectordb.pinecone_store import PineconeVectorStore

__all__ = [
    "VectorStore",
    "VectorRecord",
    "VectorHit",
    "PgVectorStore",
    "PineconeVectorStore",
    "build_vector_store",
    "MilvusManager",
]
