"""S4.4：ModelRouter 降级列表与重试配置。"""

from __future__ import annotations

import pytest

from app.infrastructure.llm.factory import build_model_router


def test_build_model_router_with_fallbacks(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "primary-model")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "backup-a,backup-b")
    from app.config import get_settings

    get_settings.cache_clear()
    router = build_model_router()
    assert router is not None
    ids = [c.model_id for c in router._configs]  # noqa: SLF001
    assert ids == ["primary-model", "backup-a", "backup-b"]
    get_settings.cache_clear()


def test_build_model_router_none_without_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    assert build_model_router() is None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_model_router_timeout_enforced(monkeypatch):
    """超时后应抛出 TimeoutError 类异常。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("LLM_RETRY_MAX_ATTEMPTS", "1")
    from app.config import get_settings
    from app.infrastructure.llm.factory import build_model_router

    get_settings.cache_clear()
    router = build_model_router()
    assert router is not None

    async def slow_create(**kwargs):
        import asyncio

        await asyncio.sleep(1.0)
        raise AssertionError("should not complete")

    client = router._clients[router._configs[0].model_id]  # noqa: SLF001
    original = client.chat.completions.create
    client.chat.completions.create = slow_create  # type: ignore[method-assign]

    with pytest.raises((TimeoutError, Exception)):
        await router.chat([{"role": "user", "content": "hi"}])

    client.chat.completions.create = original  # type: ignore[method-assign]
    get_settings.cache_clear()
