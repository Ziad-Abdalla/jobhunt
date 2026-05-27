from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime

import httpx


@dataclass(slots=True)
class RawJob:
    """Source-shaped job before normalization/extraction."""

    source: str
    source_id: str
    url: str
    company: str
    title: str
    location: str = ""
    description: str = ""
    posted_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    # Structured fields — populated when the API provides them directly.
    employment_type: str = ""  # full-time, part-time, contract, internship
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = ""
    remote_structured: str = ""  # when the API gives us remote/onsite/hybrid directly


class BaseScraper(abc.ABC):
    source: str = ""  # subclasses override

    def __init__(self, client: httpx.AsyncClient, board: str) -> None:
        self.client = client
        self.board = board  # the board token / company slug / etc.

    @abc.abstractmethod
    async def fetch(self) -> AsyncIterator[RawJob]:
        """Yield RawJob instances. Implementations are async generators."""
        raise NotImplementedError
        yield  # pragma: no cover  — makes type checkers happy
