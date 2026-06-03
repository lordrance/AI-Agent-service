"""按租户维护 BM25 内存索引（LRU 驱逐 + 文档数上限）。"""

from __future__ import annotations

from collections import OrderedDict

from loguru import logger

from app.config import get_settings
from app.core.rag.retriever import _BM25Index


class TenantBm25Registry:
    """租户级 BM25 索引注册表。"""

    def __init__(self, max_docs_per_tenant: int | None = None, max_tenants: int = 128) -> None:
        settings = get_settings()
        self._max_docs = max_docs_per_tenant or settings.rag_bm25_max_docs_per_tenant
        self._max_tenants = max_tenants
        self._indexes: OrderedDict[str, _BM25Index] = OrderedDict()
        self._texts: dict[str, dict[str, str]] = {}

    def _touch(self, tenant_id: str) -> _BM25Index:
        if tenant_id in self._indexes:
            self._indexes.move_to_end(tenant_id)
            return self._indexes[tenant_id]
        while len(self._indexes) >= self._max_tenants:
            evicted, _ = self._indexes.popitem(last=False)
            self._texts.pop(evicted, None)
            logger.debug("BM25 LRU 驱逐租户 {}", evicted)
        idx = _BM25Index()
        self._indexes[tenant_id] = idx
        self._texts[tenant_id] = {}
        return idx

    def replace_tenant_corpus(self, tenant_id: str, id_to_text: dict[str, str]) -> None:
        """全量替换某租户语料。"""
        if len(id_to_text) > self._max_docs:
            logger.warning(
                "租户 {} BM25 语料 {} 条超过上限 {}，截断",
                tenant_id,
                len(id_to_text),
                self._max_docs,
            )
            id_to_text = dict(list(id_to_text.items())[: self._max_docs])
        idx = self._touch(tenant_id)
        idx.clear()
        texts: dict[str, str] = {}
        for doc_id, text in id_to_text.items():
            idx.add_document(doc_id, text)
            texts[doc_id] = text
        self._texts[tenant_id] = texts

    def add_chunks(self, tenant_id: str, chunks: dict[str, str]) -> None:
        """增量添加分块（上传时调用）。"""
        idx = self._touch(tenant_id)
        texts = self._texts.setdefault(tenant_id, {})
        for doc_id, text in chunks.items():
            if doc_id in texts:
                continue
            if len(texts) >= self._max_docs:
                logger.warning("租户 {} BM25 已达上限，跳过新分块", tenant_id)
                return
            idx.add_document(doc_id, text)
            texts[doc_id] = text

    def remove_ids(self, tenant_id: str, ids: list[str]) -> None:
        """删除分块后重建该租户索引。"""
        texts = self._texts.get(tenant_id, {})
        for cid in ids:
            texts.pop(cid, None)
        self.replace_tenant_corpus(tenant_id, texts)

    def search(self, tenant_id: str, query: str, top_k: int) -> list[tuple[str, float]]:
        idx = self._indexes.get(tenant_id)
        if idx is None:
            return []
        return idx.search(query, top_k)

    def get_text(self, tenant_id: str, doc_id: str) -> str:
        return self._texts.get(tenant_id, {}).get(doc_id, "")

    def has_corpus(self, tenant_id: str) -> bool:
        return bool(self._texts.get(tenant_id))
