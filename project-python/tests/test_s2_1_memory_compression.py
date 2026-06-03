"""S2.1：短期记忆滑动窗口与超量压缩。"""

from __future__ import annotations

import pytest

from app.core.memory.short_term import ShortTermMemory
from app.models.enums import MessageRole
from app.models.schemas import Message


class _FakeRedis:
    """内存 Redis 列表模拟。"""

    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return list(self._lists.get(key, []))

    async def rpush(self, key: str, value: str) -> None:
        self._lists.setdefault(key, []).append(value)

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def delete(self, key: str) -> None:
        self._lists.pop(key, None)


class _FakeLLM:
    async def ainvoke(self, prompt: str, **kwargs):
        class _R:
            content = "历史对话已压缩为摘要。"

        return _R()


@pytest.mark.asyncio
async def test_short_term_compresses_when_over_window():
    redis = _FakeRedis()
    stm = ShortTermMemory(redis, _FakeLLM(), window_size=4, max_tokens=50_000)

    session = "sess-compress"
    for i in range(8):
        await stm.add_message(
            session,
            Message(role=MessageRole.USER, content=f"消息{i}：" + ("x" * 20)),
        )

    history = await stm.get_history(session)
    assert len(history) < 8
    assert any("[历史摘要]" in m.content for m in history)


@pytest.mark.asyncio
async def test_short_term_keeps_recent_tail_after_compress():
    redis = _FakeRedis()
    stm = ShortTermMemory(redis, _FakeLLM(), window_size=3, max_tokens=50_000)
    session = "sess-tail"
    for i in range(6):
        await stm.add_message(
            session,
            Message(role=MessageRole.USER, content=f"turn-{i}"),
        )

    history = await stm.get_history(session)
    contents = " ".join(m.content for m in history)
    assert "turn-5" in contents
