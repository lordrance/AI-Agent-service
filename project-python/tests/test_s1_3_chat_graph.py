"""S1.3 验证：LangGraph 对话图 + AsyncPostgresSaver 检查点跨实例保持会话。

用确定性假模型避免依赖真实 LLM；用真实 Postgres 检查点，验证「新建图实例
（模拟重启）后，同一 thread_id 仍能读到此前轮次」。
"""

from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.config import get_settings
from app.core.langgraph.graph import build_chat_graph, run_chat
from app.infrastructure.vectordb.pgvector_store import _to_asyncpg_dsn


async def _echo_model(messages: list[BaseMessage]) -> BaseMessage:
    """假模型：回显「收到 N 条消息」，N 含历史，可据此判断历史是否被续接。"""
    return AIMessage(content=f"收到 {len(messages)} 条消息")


def test_build_chat_graph_without_checkpointer_runs():
    """无检查点也能跑通一轮（不持久化）。"""
    import asyncio

    graph = build_chat_graph(_echo_model, checkpointer=None)
    out = asyncio.run(run_chat(graph, "t1", [HumanMessage(content="你好")]))
    # 1 条输入 -> 模型看到 1 条
    assert out == "收到 1 条消息"


@pytest.mark.asyncio
async def test_checkpoint_persists_across_graph_instances(require_db):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    dsn = _to_asyncpg_dsn(get_settings().database_url)
    thread_id = f"thr_{uuid.uuid4().hex[:8]}"

    # 第一段：新建 saver + 图，跑第一轮
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        graph1 = build_chat_graph(_echo_model, checkpointer=saver)
        out1 = await run_chat(graph1, thread_id, [HumanMessage(content="第一轮")])
        assert out1 == "收到 1 条消息"  # human1

    # 第二段：模拟重启——全新 saver + 全新图实例，同一 thread
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver2:
        graph2 = build_chat_graph(_echo_model, checkpointer=saver2)
        out2 = await run_chat(graph2, thread_id, [HumanMessage(content="第二轮")])
        # 历史应被续接：human1, ai1, human2 -> 模型看到 3 条
        assert out2 == "收到 3 条消息"

        # 校验最终状态包含 4 条消息（human1, ai1, human2, ai2）
        state = await graph2.aget_state(
            {"configurable": {"thread_id": thread_id}}
        )
        assert len(state.values["messages"]) == 4
        await saver2.adelete_thread(thread_id)
