"""BM25 租户注册表的同步/陈旧检测（多 worker 一致性修复）。"""

from __future__ import annotations

from app.core.rag.bm25_registry import TenantBm25Registry


def test_doc_count_and_is_synced_basic():
    reg = TenantBm25Registry(max_docs_per_tenant=100)
    reg.replace_tenant_corpus("t1", {"a": "x", "b": "y"})
    assert reg.doc_count("t1") == 2
    # 与数据库条数一致 -> 已同步
    assert reg.is_synced("t1", 2)
    # 数据库多了一条（其它 worker 上传）-> 陈旧，应触发重建
    assert not reg.is_synced("t1", 3)


def test_is_synced_caps_at_per_tenant_limit():
    """数据库分块数超过上限时，内存保留上限条即视为同步，避免每次查询都重建。"""
    reg = TenantBm25Registry(max_docs_per_tenant=2)
    reg.replace_tenant_corpus("t1", {"a": "x", "b": "y", "c": "z"})
    assert reg.doc_count("t1") == 2  # 已按上限截断
    assert reg.is_synced("t1", 3)


def test_replace_with_empty_clears_corpus():
    """数据库已无该租户分块时，用空语料替换应清空内存索引。"""
    reg = TenantBm25Registry()
    reg.replace_tenant_corpus("t1", {"a": "x"})
    assert reg.has_corpus("t1")
    reg.replace_tenant_corpus("t1", {})
    assert not reg.has_corpus("t1")
    assert reg.doc_count("t1") == 0
    assert reg.is_synced("t1", 0)
