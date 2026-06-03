"""Alembic 迁移环境：绑定应用 ORM 元数据，使用同步驱动执行迁移。"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 确保可导入 app.*（alembic 通常从 project-python 目录运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings  # noqa: E402
from app.infrastructure.database.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """将应用的异步数据库 URL 转为 alembic 用的同步驱动 URL。"""
    url = get_settings().database_url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连库。"""
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连库执行迁移。"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
