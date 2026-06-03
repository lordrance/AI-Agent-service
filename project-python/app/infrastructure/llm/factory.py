# -*- coding: utf-8 -*-
"""ModelRouter 工厂：主模型 + 降级列表 + 韧性参数。"""

from __future__ import annotations

from app.config import get_settings
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter


def build_model_router() -> ModelRouter | None:
    """按配置构造多模型路由器；无 API Key 时返回 None。"""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    model_ids: list[str] = []
    for mid in (settings.openai_model, *settings.fallback_model_list()):
        if mid and mid not in model_ids:
            model_ids.append(mid)

    configs = [
        ModelConfig(
            model_id=mid,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base or None,
            priority=idx,
        )
        for idx, mid in enumerate(model_ids)
    ]
    return ModelRouter(
        configs,
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout=settings.circuit_breaker_recovery_timeout,
        request_timeout=settings.llm_timeout_seconds,
        max_tokens_cap=settings.llm_max_tokens_per_request,
        retry_attempts=settings.llm_retry_max_attempts,
    )
