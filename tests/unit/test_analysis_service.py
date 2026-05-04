from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.analysis_service import AnalysisService


class FakeRepo:
    def __init__(self, rows: list[tuple[date, str, Decimal | None, int]]) -> None:
        self._rows = rows

    async def add(self, entry):  # pragma: no cover
        raise NotImplementedError

    async def list_range(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    async def daily_aggregates(self, user_id, start, end):
        return self._rows


async def test_daily_summary_pivots_rows() -> None:
    rows = [
        (date(2026, 5, 1), "mood", Decimal("6"), 1),
        (date(2026, 5, 1), "energy", Decimal("4"), 1),
        (date(2026, 5, 2), "mood", Decimal("8"), 2),
        (date(2026, 5, 2), "energy", Decimal("5"), 1),
        # Free-text rows are filtered out:
        (date(2026, 5, 2), "note", None, 3),
    ]
    svc = AnalysisService(FakeRepo(rows))
    df = await svc.daily_summary(1, date(2026, 5, 1), date(2026, 5, 2))

    assert list(df.columns) == sorted(df.columns)
    assert "mood" in df.columns and "energy" in df.columns
    assert "note" not in df.columns
    assert df.loc[df.index[0], "mood"] == 6.0
    assert df.loc[df.index[1], "mood"] == 8.0


async def test_daily_summary_empty() -> None:
    svc = AnalysisService(FakeRepo([]))
    df = await svc.daily_summary(1, date(2026, 5, 1), date(2026, 5, 2))
    assert df.empty
