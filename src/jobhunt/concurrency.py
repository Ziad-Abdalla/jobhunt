"""Bounded-concurrency helper shared by the scrape pipeline and `jobhunt doctor`.

Firing every source at once (`asyncio.gather` over the full list) is fine at 158
sources but risks 429s / WAF blocks once we ship 30+ new ones — especially when
many share a host. `gather_bounded` caps how many run at once while preserving
result order.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def gather_bounded(
    factories: list[Callable[[], Awaitable[T]]], limit: int
) -> list[T]:
    """Run each zero-arg async factory with at most `limit` in flight at once.

    Results are returned in the same order as `factories`. `limit` is floored at 1.
    """
    sem = asyncio.Semaphore(max(1, limit))

    async def _run(factory: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            return await factory()

    return await asyncio.gather(*[_run(f) for f in factories])
