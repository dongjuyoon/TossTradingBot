from __future__ import annotations

import pytest

from ai_swing_bot.market.rate_limit import AsyncRateLimiter


@pytest.mark.anyio
async def test_rate_limiter_spaces_requests() -> None:
    now = 100.0
    delays: list[float] = []

    def clock() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    limiter = AsyncRateLimiter(2, clock=clock, sleep=sleep)
    await limiter.wait()
    await limiter.wait()
    await limiter.wait()
    assert delays == [0.5, 0.5]
