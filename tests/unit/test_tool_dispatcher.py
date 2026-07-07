from __future__ import annotations

from datetime import UTC, date, datetime

from app.ai.tools import ToolDispatcher
from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO


class _FakeEntryService:
    def __init__(self, rows: list[EntryDTO]) -> None:
        self._rows = rows

    async def list_range(
        self, user_id: int, start: date, end: date, metric_types=None
    ) -> list[EntryDTO]:
        return list(self._rows)


def _dto(recorded_at: datetime, entry_date: date, metric: MetricType, num=None, text=None) -> EntryDTO:
    return EntryDTO(
        id=1,
        recorded_at=recorded_at,
        entry_date=entry_date,
        metric_type=metric,
        value_numeric=num,
        value_text=text,
        tags=None,
        extra=None,
    )


def _dispatcher(rows: list[EntryDTO], tz: str = "Europe/Belgrade") -> ToolDispatcher:
    return ToolDispatcher(
        user_id=1,
        user_timezone=tz,
        entry_service=_FakeEntryService(rows),  # type: ignore[arg-type]
        analysis_service=None,  # type: ignore[arg-type]
        chart_service=None,  # type: ignore[arg-type]
        pdf_service=None,  # type: ignore[arg-type]
    )


async def test_query_entries_localizes_timestamp() -> None:
    # 22:30 UTC on 2026-05-04 is 00:30 the next day in Europe/Belgrade (CEST, UTC+2).
    rec = datetime(2026, 5, 4, 22, 30, tzinfo=UTC)
    disp = _dispatcher([_dto(rec, date(2026, 5, 5), MetricType.MOOD, num=7.0)])

    out = await disp.call(
        "query_entries", {"start_date": "2026-05-04", "end_date": "2026-05-05"}
    )

    entry = out["entries"][0]
    assert entry["time"] == "00:30"
    assert entry["date"] == "2026-05-05"
    assert entry["value_numeric"] == 7.0
    # Localized full timestamp carries the local offset, not Z/UTC.
    assert entry["recorded_at"].startswith("2026-05-05T00:30")


async def test_query_entries_preserves_chronological_order() -> None:
    rows = [
        _dto(datetime(2026, 5, 4, 6, 0, tzinfo=UTC), date(2026, 5, 4), MetricType.MOOD, num=5.0),
        _dto(datetime(2026, 5, 4, 9, 0, tzinfo=UTC), date(2026, 5, 4), MetricType.NOTE, text="rough morning"),
    ]
    disp = _dispatcher(rows)
    out = await disp.call(
        "query_entries", {"start_date": "2026-05-04", "end_date": "2026-05-04"}
    )
    times = [e["time"] for e in out["entries"]]
    assert times == sorted(times)
