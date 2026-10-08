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


async def test_migraine_stats_tool() -> None:
    from app.ai.tools import TOOL_SCHEMAS

    schema = next(s for s in TOOL_SCHEMAS if s["name"] == "migraine_stats")
    assert "user_id" not in schema["input_schema"]["properties"]

    start = datetime(2026, 5, 3, 9, 0, tzinfo=UTC)
    attack = EntryDTO(
        id=5, recorded_at=start, entry_date=date(2026, 5, 3),
        metric_type=MetricType.MIGRAINE, value_numeric=7.0, value_text=None, tags=None,
        extra={"status": "ended", "started_at": start.isoformat(),
               "ended_at": datetime(2026, 5, 3, 15, 0, tzinfo=UTC).isoformat(),
               "duration_minutes": 360, "start_intensity": 5, "peak_intensity": 7,
               "symptoms": ["nausea"], "triggers": ["sleep"],
               "medication_text": "ibuprofen", "relief": 6},
    )
    disp = _dispatcher([attack], tz="UTC")
    out = await disp.call(
        "migraine_stats", {"start_date": "2026-05-01", "end_date": "2026-05-07"}
    )
    assert out["attacks"] == 1
    assert out["headache_days"] == 1
    assert out["avg_duration_minutes"] == 360
    assert out["medications"][0]["name"] == "ibuprofen"
    assert "medication_days_last_30" in out



async def test_query_entries_includes_local_weekday() -> None:
    # 22:30 UTC Mon 2026-05-04 is 00:30 Tue 2026-05-05 in Belgrade.
    rec = datetime(2026, 5, 4, 22, 30, tzinfo=UTC)
    disp = _dispatcher([_dto(rec, date(2026, 5, 5), MetricType.MOOD, num=7.0)])
    out = await disp.call("query_entries", {"start_date": "2026-05-04", "end_date": "2026-05-05"})
    assert out["entries"][0]["weekday"] == "Tue"


async def test_daily_summary_includes_weekday() -> None:
    import pandas as pd

    class _Analysis:
        async def daily_summary(self, user_id, start, end):
            return pd.DataFrame({"mood": [6.0]}, index=pd.to_datetime(["2026-05-05"]))

    disp = _dispatcher([])
    disp.analysis_service = _Analysis()  # type: ignore[assignment]
    out = await disp.call("daily_summary", {"start_date": "2026-05-05", "end_date": "2026-05-05"})
    assert out["days"][0]["weekday"] == "Tue"
