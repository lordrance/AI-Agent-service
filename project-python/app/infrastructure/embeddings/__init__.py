"""嵌入器抽象与工厂。"""

from app.infrastructure.embeddings.base import Embedder
from app.infrastructure.embeddings.factory import get_embedder

__all__ = ["Embedder", "get_embedder"]
