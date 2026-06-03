"""knowledge_vectors table for pgvector

Revision ID: 0002_knowledge_vectors
Revises: 9118ab9badea
Create Date: 2026-06-03

注意：embedding 维度固定为 1536，须与 settings.embedding_dim 默认值一致；
若更换嵌入模型导致维度变化，请新增迁移而非修改本文件。
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_knowledge_vectors"
down_revision: Union[str, None] = "9118ab9badea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
        CREATE TABLE knowledge_vectors (
            id varchar(64) PRIMARY KEY,
            document_id varchar(64),
            content text NOT NULL,
            metadata jsonb,
            embedding vector({_DIM}) NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_knowledge_vectors_document_id ON knowledge_vectors (document_id)")
    op.execute(
        "CREATE INDEX ix_knowledge_vectors_embedding ON knowledge_vectors "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_vectors")
