"""Shared in-memory fakes for unit tests (no Postgres)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.domain.models import Entry


class FakeEntryRepo:
    """In-memory EntryRepository. Mirrors SqlEntryRepository semantics:
    user-scoped reads, inclusive date range, chronological order."""

    def __init__(self) -> None:
        self.rows: list[Entry] = []
        self._next = 1

    async def add(self, entry: Entry) -> Entry:
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(
        self,
        user_id: int,
        start: date,
        end: date,
        metric_types: list[str] | None = None,
    ) -> list[Entry]:
        out = [
            r for r in self.rows
            if r.user_id == user_id and start <= r.entry_date <= end
        ]
        if metric_types:
            out = [r for r in out if r.metric_type in metric_types]
        return sorted(out, key=lambda r: r.recorded_at)

    async def daily_aggregates(
        self, user_id: int, start: date, end: date
    ) -> list[tuple[date, str, Decimal | None, int]]:
        groups: dict[tuple[date, str], list[Decimal]] = defaultdict(list)
        for r in await self.list_range(user_id, start, end):
            if r.value_numeric is not None:
                groups[(r.entry_date, r.metric_type)].append(r.value_numeric)
        return [
            (d, m, sum(vs) / len(vs), len(vs))
            for (d, m), vs in sorted(groups.items())
        ]

    async def get_for_user(self, entry_id: int, user_id: int) -> Entry | None:
        for r in self.rows:
            if r.id == entry_id and r.user_id == user_id:
                return r
        return None

    async def exists(self, entry_id: int) -> bool:
        return any(r.id == entry_id for r in self.rows)

    async def delete(self, entry: Entry) -> None:
        self.rows = [r for r in self.rows if r is not entry]
