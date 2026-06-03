"""documents 表增加 tenant_id 列

Revision ID: 0003_tenant_id
Revises: 0002_knowledge_vectors
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_tenant_id"
down_revision = "0002_knowledge_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("tenant_id", sa.String(length=128), nullable=False, server_default="anonymous"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_column("documents", "tenant_id")
