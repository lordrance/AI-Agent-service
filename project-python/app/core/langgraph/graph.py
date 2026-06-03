"""对话状态图：单节点调用模型，状态经检查点持久化以支持多轮会话。

- 状态 `messages` 使用 LangGraph 的 `add_messages` reducer 累积消息；
- 模型节点通过注入的 `ModelFn` 调用 LLM，便于在测试中替换为确定性假实现；
- 编译时传入 `AsyncPostgresSaver` 检查点，按 `thread_id` 隔离/恢复会话，跨进程重启不丢。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

ModelFn = Callable[[list[BaseMessage]], Awaitable[BaseMessage]]


class ChatState(TypedDict):
    """对话图状态。"""

    messages: Annotated[list[AnyMessage], add_messages]


def build_chat_graph(model_fn: ModelFn, checkpointer=None):
    """构造并编译对话图。

    :param model_fn: 异步模型函数，输入完整消息历史，返回助手消息。
    :param checkpointer: LangGraph 检查点（如 AsyncPostgresSaver）；None 则不持久化。
    """
    builder = StateGraph(ChatState)

    async def chat_node(state: ChatState) -> dict:
        reply = await model_fn(list(state["messages"]))
        if not isinstance(reply, BaseMessage):
            reply = AIMessage(content=str(reply))
        return {"messages": [reply]}

    builder.add_node("chat", chat_node)
    builder.set_entry_point("chat")
    builder.add_edge("chat", END)
    return builder.compile(checkpointer=checkpointer)


async def run_chat_turn(graph, thread_id: str, user_text: str) -> str:
    """执行一轮对话并返回助手回复文本（自动按 thread_id 续接历史）。"""
    return await run_chat(graph, thread_id, [HumanMessage(content=user_text)])


async def run_chat(graph, thread_id: str, messages: list[BaseMessage]) -> str:
    """以一组消息驱动一轮对话，按 thread_id 续接历史并返回助手回复文本。"""
    result = await graph.ainvoke(
        {"messages": messages},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 10},
    )
    last = result["messages"][-1]
    return last.content if isinstance(last, BaseMessage) else str(last)
