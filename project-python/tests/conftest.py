"""测试夹具与工具：数据库可达性检测（不可达则跳过依赖 DB 的用例）。"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from app.config import get_settings
from app.infrastructure.vectordb.pgvector_store import _to_asyncpg_dsn


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(_to_asyncpg_dsn(get_settings().database_url))
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_available() -> bool:
    return _db_reachable()


@pytest.fixture
def require_db(db_available: bool) -> None:
    if not db_available:
        pytest.skip("PostgreSQL/pgvector 不可达，跳过依赖 DB 的用例")
