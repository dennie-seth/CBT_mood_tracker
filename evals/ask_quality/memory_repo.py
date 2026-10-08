"""In-memory EntryRepository for the eval (fresh per trial, no Postgres).

Same semantics as SqlEntryRepository: user-scoped, inclusive date range,
chronological order, per-day numeric averages.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any


class MemoryEntryRepo:
    def __init__(self) -> None:
        self.rows: list[Any] = []
        self._next = 1

    async def add(self, entry: Any) -> Any:
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(self, user_id: int, start: date, end: date,
                         metric_types: list[str] | None = None) -> list[Any]:
        out = [r for r in self.rows if r.user_id == user_id and start <= r.entry_date <= end]
        if metric_types:
            out = [r for r in out if r.metric_type in metric_types]
        return sorted(out, key=lambda r: r.recorded_at)

    async def daily_aggregates(self, user_id: int, start: date, end: date) -> list[Any]:
        groups: dict[tuple[date, str], list[Decimal]] = defaultdict(list)
        for r in await self.list_range(user_id, start, end):
            if r.value_numeric is not None:
                groups[(r.entry_date, r.metric_type)].append(r.value_numeric)
        return [(d, m, sum(v) / len(v), len(v)) for (d, m), v in sorted(groups.items())]

    async def get_for_user(self, entry_id: int, user_id: int) -> Any:
        return next((r for r in self.rows if r.id == entry_id and r.user_id == user_id), None)

    async def exists(self, entry_id: int) -> bool:
        return any(r.id == entry_id for r in self.rows)

    async def delete(self, entry: Any) -> None:
        self.rows = [r for r in self.rows if r is not entry]
