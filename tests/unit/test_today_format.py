"""/today and /week render migraine attacks as one informative line
(time span, duration, peak, medication) instead of a bare number."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.bot.handlers.today import _format_entries
from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO

NOW = datetime(2026, 10, 8, 20, 0, tzinfo=UTC)


def _dto(metric: MetricType, value: float | None, extra=None, text=None) -> EntryDTO:
    return EntryDTO(
        id=1, recorded_at=NOW - timedelta(hours=6), entry_date=date(2026, 10, 8),
        metric_type=metric, value_numeric=value, value_text=text, tags=None, extra=extra,
    )


def test_migraine_attack_line() -> None:
    attack = _dto(MetricType.MIGRAINE, 7, {
        "status": "ended",
        "started_at": (NOW - timedelta(hours=6)).isoformat(),
        "ended_at": (NOW - timedelta(hours=1)).isoformat(),
        "duration_minutes": 300, "start_intensity": 5, "peak_intensity": 7,
        "medication_text": "ibuprofen", "relief": 6,
    })
    out = _format_entries([attack, _dto(MetricType.MOOD, 6)], "Today", "en", "today.empty",
                          tz="UTC", now=NOW)
    assert "14:00–19:00 (5h 0m), peak 7; ibuprofen → helped 6/10" in out
    assert "Mood" in out and "6" in out


def test_plain_backfilled_migraine_still_shows_value() -> None:
    out = _format_entries([_dto(MetricType.MIGRAINE, 6)], "Today", "en", "today.empty",
                          tz="UTC", now=NOW)
    assert "Migraine" in out and "6" in out
