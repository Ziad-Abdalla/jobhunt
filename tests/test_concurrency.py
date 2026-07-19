import asyncio

import pytest

from jobhunt.concurrency import gather_bounded


@pytest.mark.asyncio
async def test_gather_bounded_caps_concurrency_and_preserves_order():
    current = 0
    peak = 0

    async def task(i: int) -> int:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.01)
        current -= 1
        return i

    results = await gather_bounded([lambda i=i: task(i) for i in range(12)], limit=3)

    assert results == list(range(12))  # order preserved despite bounded scheduling
    assert peak <= 3  # never more than `limit` in flight at once


@pytest.mark.asyncio
async def test_gather_bounded_limit_one_runs_serially():
    current = 0
    peak = 0

    async def task(i: int) -> int:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.005)
        current -= 1
        return i

    await gather_bounded([lambda i=i: task(i) for i in range(5)], limit=1)
    assert peak == 1
