"""Epic 0 验证：接口对齐与启动修复。

覆盖：
- S0.1 `import app.main` 成功（不再因缺 langfuse_exporter 失败）。
- S0.3 `ToolRegistry` 暴露编排器期望的 `list_tool_names()` / `invoke()`；
        `MemoryManager` 暴露 `get_relevant()` / `append_turn()`。
"""

from __future__ import annotations

import pytest

from app.core.memory.manager import MemoryManager
from app.core.tools.base import BaseTool, ToolParameter
from app.core.tools.registry import ToolRegistry
from app.models.enums import MessageRole
from app.models.schemas import MemoryContext, MemoryItem, Message


def test_import_app_main_succeeds():
    """S0.1：应用入口可导入（启动崩溃已修复）。"""
    import app.main as main

    assert main.app.title


class _EchoTool(BaseTool):
    name = "echo"
    description = "回显输入文本"

    def __init__(self) -> None:
        super().__init__()
        self.parameters = [ToolParameter(name="text", type="string", description="文本")]

    async def execute(self, **kwargs):
        return f"echo: {kwargs.get('text', '')}"


@pytest.mark.asyncio
async def test_tool_registry_orchestrator_protocol():
    """S0.3：ToolRegistry 满足编排器协议（list_tool_names / invoke）。"""
    reg = ToolRegistry()
    reg.register(_EchoTool())

    assert reg.list_tool_names() == ["echo"]

    ok = await reg.invoke("echo", {"text": "hi"})
    assert ok == "echo: hi"

    # 未注册工具：返回可读错误串而非抛异常
    err = await reg.invoke("nope", {})
    assert "未注册" in err or "错误" in err


class _FakeSTM:
    """伪短期记忆：内存列表。"""

    def __init__(self) -> None:
        self.store: dict[str, list[Message]] = {}

    async def get_history(self, session_id: str) -> list[Message]:
        return list(self.store.get(session_id, []))

    async def add_message(self, session_id: str, message: Message) -> None:
        self.store.setdefault(session_id, []).append(message)


class _FakeLTM:
    """伪长期记忆：固定召回。"""

    async def recall(self, query: str, session_id: str, top_k: int = 5) -> list[MemoryItem]:
        return [MemoryItem(id="m1", content=f"long-term about {query}", score=0.9)]


@pytest.mark.asyncio
async def test_memory_manager_orchestrator_protocol():
    """S0.3：MemoryManager 满足编排器协议（append_turn / get_relevant）。"""
    mgr = MemoryManager(short_term=_FakeSTM(), long_term=_FakeLTM())

    await mgr.append_turn("sess", "user", "你好")
    await mgr.append_turn("sess", "assistant", "在的")

    snippets = await mgr.get_relevant("sess", "天气", limit=8)
    # 短期两条 + 长期一条
    assert any("你好" in s for s in snippets)
    assert any("long-term about 天气" in s for s in snippets)

    # 非法角色回退为 assistant，不抛异常
    await mgr.append_turn("sess", "weird-role", "x")
    ctx: MemoryContext = await mgr.get_context("sess", "q")
    assert ctx.short_term_messages[-1].role == MessageRole.ASSISTANT
