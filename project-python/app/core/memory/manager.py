"""统一记忆管理：协调短期记忆与长期记忆。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from loguru import logger

from app.core.memory.short_term import ShortTermMemory
from app.models.enums import MessageRole
from app.models.schemas import MemoryContext, Message


@runtime_checkable
class LongTermMemoryLike(Protocol):
    async def store(self, session_id: str, content: str, metadata: dict[str, Any]) -> str: ...

    async def recall(self, query: str, session_id: str, top_k: int = 5) -> list[Any]: ...

    async def forget(self, memory_id: str) -> None: ...


class MemoryManager:
    """统一记忆管理器：协调短期记忆和长期记忆。"""

    def __init__(self, short_term: ShortTermMemory, long_term: LongTermMemoryLike) -> None:
        """
        :param short_term: 短期记忆实现（Redis + 窗口）
        :param long_term: 长期记忆实现（向量库）
        """
        self._stm = short_term
        self._ltm = long_term

    async def get_context(self, session_id: str, query: str) -> MemoryContext:
        """获取与当前查询相关的记忆上下文（短期历史 + 长期召回）。"""
        try:
            short_msgs = await self._stm.get_history(session_id)
        except Exception as e:
            logger.exception("读取短期记忆失败: {}", e)
            short_msgs = []

        try:
            long_items = await self._ltm.recall(query, session_id, top_k=5)
        except Exception as e:
            logger.exception("长期记忆召回失败: {}", e)
            long_items = []

        return MemoryContext(
            session_id=session_id,
            short_term_messages=short_msgs,
            long_term_items=long_items,
        )

    async def save(self, session_id: str, message: Message) -> None:
        """将新消息写入短期记忆（滑动窗口与压缩由 ShortTermMemory 负责）。"""
        try:
            await self._stm.add_message(session_id, message)
        except Exception as e:
            logger.exception("保存短期记忆失败: {}", e)
            raise RuntimeError(f"save 失败: {e}") from e

    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        """编排器/ReAct 适配接口：返回与查询相关的记忆片段（短期历史 + 长期召回）字符串列表。"""
        ctx = await self.get_context(session_id, query)
        snippets: list[str] = [f"{m.role.value}: {m.content}" for m in ctx.short_term_messages]
        snippets.extend(item.content for item in ctx.long_term_items)
        return snippets[:limit]

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """编排器/ReAct 适配接口：将一轮消息追加到短期记忆。"""
        try:
            role_enum = MessageRole(role)
        except ValueError:
            role_enum = MessageRole.ASSISTANT
        await self.save(
            session_id,
            Message(role=role_enum, content=content, metadata=metadata or {}),
        )
