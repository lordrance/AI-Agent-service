"""嵌入器抽象：统一 `embed_query` / `embed_documents` / `dim`。

方法为同步设计，便于复用现有 `MultiRetriever`（其内部以 `asyncio.to_thread` 包装），
也便于在向量库写入侧直接调用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Embedder(ABC):
    """文本嵌入器抽象基类。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """嵌入维度。"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """对单条查询文本编码。"""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """对一批文档文本编码。"""
