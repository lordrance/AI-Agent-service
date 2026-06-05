# -*- coding: utf-8 -*-
"""多模型路由器：优先级调度、加权选择、熔断、重试与自动降级。"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from openai import APIError, APIStatusError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.infrastructure.llm.circuit_breaker import CircuitBreaker
from app.infrastructure.llm.types import ModelProvider
from app.infrastructure.metrics.prometheus import record_llm_call
from app.infrastructure.trace.genai_otel import genai_span, record_llm_usage

_TRANSIENT_ERRORS = (RateLimitError, APIError, APIStatusError, TimeoutError, asyncio.TimeoutError)


class AllModelsUnavailableError(RuntimeError):
    """所有候选模型均不可用（熔断/鉴权失败/超时等耗尽后抛出）。

    继承 RuntimeError 以保持向后兼容；路由层可据此返回 503 而非 500。
    """


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (408, 429, 500, 502, 503, 504)
    return isinstance(exc, APIError)


class LLMResponse(BaseModel):
    """统一 LLM 响应结构。"""

    content: str = ""
    model_id: str = ""
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    finish_reason: str | None = None


@dataclass
class ModelConfig:
    """单路模型配置。"""

    model_id: str
    api_key: str
    base_url: str | None = None
    provider: ModelProvider = ModelProvider.OPENAI
    priority: int = 0
    weight: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


class ModelRouter:
    """多模型路由器：支持优先级调度、负载均衡（同优先级加权随机）、自动降级。"""

    def __init__(
        self,
        model_configs: list[ModelConfig],
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        request_timeout: float = 60.0,
        max_tokens_cap: int | None = None,
        retry_attempts: int = 3,
    ) -> None:
        if not model_configs:
            raise ValueError("model_configs 不能为空")

        self._configs = sorted(model_configs, key=lambda c: c.priority)
        self._request_timeout = max(1.0, request_timeout)
        self._max_tokens_cap = max_tokens_cap
        self._retry_attempts = max(1, retry_attempts)
        self._breakers: dict[str, CircuitBreaker] = {}
        for cfg in self._configs:
            self._breakers[cfg.model_id] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                name=f"llm:{cfg.model_id}",
            )
        self._clients: dict[str, AsyncOpenAI] = {}
        for cfg in self._configs:
            kwargs: dict[str, Any] = {"api_key": cfg.api_key}
            if cfg.base_url:
                kwargs["base_url"] = cfg.base_url
            self._clients[cfg.model_id] = AsyncOpenAI(**kwargs)

    def _select_candidates(
        self,
        model_preference: str | None,
    ) -> list[ModelConfig]:
        """按优先级分组，在同优先级内按权重随机排序，形成候选列表。"""
        if model_preference:
            exact = [c for c in self._configs if c.model_id == model_preference]
            if exact:
                return exact

        by_prio: dict[int, list[ModelConfig]] = {}
        for cfg in self._configs:
            by_prio.setdefault(cfg.priority, []).append(cfg)

        ordered: list[ModelConfig] = []
        for prio in sorted(by_prio.keys()):
            group = by_prio[prio]
            scored = [(cfg, random.random() ** (1.0 / max(cfg.weight, 0.01))) for cfg in group]
            scored.sort(key=lambda x: -x[1])
            ordered.extend(cfg for cfg, _ in scored)
        return ordered or list(self._configs)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model_preference: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """智能路由到合适模型；失败时按候选顺序自动降级。"""
        candidates = self._select_candidates(model_preference)
        last_error: Exception | None = None

        for cfg in candidates:
            breaker = self._breakers[cfg.model_id]
            try:
                return await breaker.call(
                    self._invoke_with_resilience,
                    cfg.model_id,
                    messages,
                    **kwargs,
                )
            except RuntimeError as exc:
                last_error = exc
                logger.warning("模型 [{}] 被熔断跳过: {}", cfg.model_id, exc)
                record_llm_call(cfg.model_id, success=False)
            except _TRANSIENT_ERRORS as exc:
                last_error = exc
                logger.warning("模型 [{}] 调用失败，尝试降级: {}", cfg.model_id, exc)
                record_llm_call(cfg.model_id, success=False)
            except Exception as exc:
                last_error = exc
                logger.exception("模型 [{}] 未预期错误: {}", cfg.model_id, exc)
                record_llm_call(cfg.model_id, success=False)

        msg = "所有候选模型均不可用"
        if last_error:
            raise AllModelsUnavailableError(msg) from last_error
        raise AllModelsUnavailableError(msg)

    async def _invoke_with_resilience(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        """带 OTel span、超时、tenacity 重试的模型调用。"""
        with genai_span("gen_ai.chat", model=model_id) as span:
            response = await self._call_with_retry(model_id, messages, **kwargs)
            finish = response.finish_reason or "stop"
            record_llm_usage(
                span,
                model_id=model_id,
                usage=response.usage,
                finish_reason=finish,
            )
            record_llm_call(model_id, success=True, usage=response.usage)
            return response

    async def _call_with_retry(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        attempts = self._retry_attempts

        @retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        async def _inner() -> LLMResponse:
            return await asyncio.wait_for(
                self._try_model(model_id, messages, **kwargs),
                timeout=self._request_timeout,
            )

        return await _inner()

    async def _try_model(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        """调用指定 OpenAI 兼容模型。"""
        client = self._clients[model_id]
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", None)
        if self._max_tokens_cap is not None:
            if max_tokens is None:
                max_tokens = self._max_tokens_cap
            else:
                max_tokens = min(int(max_tokens), self._max_tokens_cap)

        params: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        resp = await client.chat.completions.create(**params)

        choice = resp.choices[0] if resp.choices else None
        content = (choice.message.content or "") if choice else ""
        finish_reason = getattr(choice, "finish_reason", None) if choice else None
        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model_id=model_id,
            usage=usage,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
            finish_reason=str(finish_reason) if finish_reason else None,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model_preference: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式输出文本增量；使用首个可用候选模型。"""
        candidates = self._select_candidates(model_preference)
        if not candidates:
            raise RuntimeError("无可用模型")
        cfg = candidates[0]
        client = self._clients[cfg.model_id]
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", None)
        if self._max_tokens_cap is not None and max_tokens is not None:
            max_tokens = min(int(max_tokens), self._max_tokens_cap)

        params: dict[str, Any] = {
            "model": cfg.model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        stream = await client.chat.completions.create(**params)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
