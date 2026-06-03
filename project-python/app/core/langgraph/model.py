"""生产模型函数：复用现有 ModelRouter（OpenAI 兼容 + 熔断/降级）驱动对话图节点。"""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage

from app.config import get_settings
from app.core.langgraph.graph import ModelFn
from app.infrastructure.llm.factory import build_model_router

_ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}


def _to_openai_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """把 LangChain 消息转为 OpenAI 风格 messages。"""
    out: list[dict[str, str]] = []
    for m in messages:
        role = _ROLE_MAP.get(getattr(m, "type", "human"), "user")
        out.append({"role": role, "content": str(m.content)})
    return out


def build_router_model_fn() -> ModelFn | None:
    """构造基于 ModelRouter 的模型函数；未配置 API Key 时返回 None。"""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    router = build_model_router()
    if router is None:
        return None

    async def model_fn(messages: list[BaseMessage]) -> BaseMessage:
        resp = await router.chat(_to_openai_messages(messages))
        return AIMessage(content=resp.content)

    return model_fn
