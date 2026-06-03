"""S2.1：熔断器三态转换与快速失败。"""

from __future__ import annotations

import time

import pytest

from app.infrastructure.llm.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_breaker_closed_on_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.2, name="t-closed")

    async def ok() -> str:
        return "ok"

    assert await cb.call(ok) == "ok"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="t-open")

    async def fail() -> None:
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)

    assert cb.state == CircuitState.OPEN

    async def ok() -> str:
        return "x"

    with pytest.raises(RuntimeError, match="OPEN"):
        await cb.call(ok)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=0.05,
        half_open_max=2,
        name="t-half",
    )

    async def fail() -> None:
        raise ValueError("down")

    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    # 模拟已过恢复窗口（避免 CI 计时抖动）
    cb._last_failure_time = time.monotonic() - cb.recovery_timeout - 0.01

    async def ok() -> str:
        return "recovered"

    result = await cb.call(ok)
    assert result == "recovered"
    assert cb.state == CircuitState.CLOSED
