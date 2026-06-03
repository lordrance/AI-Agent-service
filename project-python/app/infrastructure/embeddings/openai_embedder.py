"""OpenAI / 兼容嵌入后端（同步客户端，便于在线程池中复用）。"""

from __future__ import annotations

from loguru import logger
from openai import OpenAI


class OpenAIEmbedder:
    """调用 OpenAI 兼容 `embeddings` 接口的嵌入器。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        dim: int,
        base_url: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAIEmbedder 需要 api_key")
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = self._client.embeddings.create(model=self._model, input=texts)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI 嵌入调用失败 model={}", self._model)
            raise RuntimeError(f"嵌入失败: {exc}") from exc
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)
