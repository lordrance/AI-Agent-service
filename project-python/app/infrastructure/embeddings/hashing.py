"""本地确定性哈希嵌入器：无外部依赖、可离线、结果稳定。

用途：开发/测试与无密钥环境下验证向量库与检索链路。它把文本分词后用
哈希分桶到固定维度并做 TF 加权与 L2 归一化；语义近似来自词重叠，足以验证
「写入→相似度检索」的正确性，但不具备真正的语义理解（生产请用 openai 后端）。
"""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t]


class HashingEmbedder:
    """哈希分桶嵌入（确定性）。"""

    def __init__(self, dim: int = 1536) -> None:
        if dim <= 0:
            raise ValueError("dim 必须为正整数")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = _tokenize(text)
        for tok in tokens:
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self._dim
            # 次字节决定符号，降低不同词哈希到同桶时的相互抵消偏差
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
