from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.models import Entry, User


class UserRepository(Protocol):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...
    async def create(self, telegram_id: int, display_name: str | None, timezone: str) -> User: ...
    async def update_timezone(self, user_id: int, timezone: str) -> None: ...


class EntryRepository(Protocol):
    async def add(self, entry: Entry) -> Entry: ...

    async def list_range(
        self,
        user_id: int,
        start: date,
        end: date,
        metric_types: list[str] | None = None,
    ) -> list[Entry]: ...

    async def daily_aggregates(
        self,
        user_id: int,
        start: date,
        end: date,
    ) -> list[tuple[date, str, Decimal | None, int]]:
        """Returns (entry_date, metric_type, avg_numeric, count) tuples."""
        ...

    async def get_for_user(self, entry_id: int, user_id: int) -> Entry | None:
        """Load by id with an ownership filter — single chokepoint for AuthZ
        on entry mutation. Returns None if the entry doesn't exist OR belongs
        to another user."""
        ...

    async def exists(self, entry_id: int) -> bool:
        """Existence probe (no row data) — used purely to discriminate
        'not yours' from 'doesn't exist' when an authorisation check fails."""
        ...


__all__ = [
    "UserRepository",
    "EntryRepository",
    "User",
    "Entry",
]
