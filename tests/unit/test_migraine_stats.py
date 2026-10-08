"""compute_stats: pure summary of migraine attacks for /migraines, the AI
tool and the therapist PDF. Counts, not averages, drive frequency."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO
from app.services.migraine_stats import MEDICATION_DAYS_FLAG, compute_stats

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
START, END = date(2026, 9, 9), date(2026, 10, 8)
_ids = iter(range(1, 1000))


def _attack(start: datetime, *, hours: float | None = 5, peak: int = 6, **extra) -> EntryDTO:
    x = {
        "status": "ended" if hours is not None else "ongoing",
        "started_at": start.isoformat(), "start_intensity": peak, "peak_intensity": peak,
        "aura": False, "symptoms": [], "triggers": [], **extra,
    }
    if hours is not None:
        x["ended_at"] = (start + timedelta(hours=hours)).isoformat()
        x["duration_minutes"] = int(hours * 60)
    return EntryDTO(
        id=next(_ids), recorded_at=start, entry_date=start.date(),
        metric_type=MetricType.MIGRAINE, value_numeric=float(peak),
        value_text=None, tags=None, extra=x,
    )


def _d(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=UTC)


def test_empty() -> None:
    s = compute_stats([], start=START, end=END, tz_name="UTC", now=NOW)
    assert s.attacks == 0 and s.headache_days == 0
    assert s.avg_duration_minutes is None and s.avg_peak is None
    assert s.medications == []


def test_counts_and_averages() -> None:
    attacks = [
        _attack(_d(1), hours=4, peak=5, aura=True, symptoms=["nausea", "light"],
                triggers=["sleep"], medication_text="Ibuprofen 400", relief=4),
        _attack(_d(3), hours=30, peak=8, symptoms=["nausea"], triggers=["sleep", "stress"],
                medication_text="sumatriptan 50", relief=8),
        _attack(_d(6), hours=None, peak=7, medication_text="ibuprofen 400"),  # ongoing
    ]
    s = compute_stats(attacks, start=START, end=END, tz_name="UTC", now=NOW)

    assert s.attacks == 3
    assert s.open_attacks == 1
    # Oct 1; Oct 3-4 (30h spans midnight); Oct 6-8 (ongoing until now).
    assert s.headache_days == 6
    assert s.avg_duration_minutes == 17 * 60  # ended attacks only
    assert s.longest_minutes == 30 * 60
    assert s.avg_peak == 6.7
    assert s.max_peak == 8
    assert s.aura == 1
    assert s.symptoms == {"nausea": 2, "light": 1}
    assert list(s.triggers) == ["sleep", "stress"]  # most common first
    assert s.medication_days == 3
    meds = {m.name.lower(): m for m in s.medications}
    assert meds["ibuprofen 400"].attacks == 2
    assert meds["ibuprofen 400"].avg_relief == 4.0
    assert meds["ibuprofen 400"].rated == 1
    assert meds["sumatriptan 50"].avg_relief == 8.0


def test_headache_days_clipped_to_range_and_tz() -> None:
    # 23:00 UTC Sep 8 is Sep 9 01:00 in Berlin → inside the range.
    a = _attack(datetime(2026, 9, 8, 23, 0, tzinfo=UTC), hours=2)
    s = compute_stats([a], start=START, end=END, tz_name="Europe/Berlin", now=NOW)
    assert s.headache_days == 1


def test_backfilled_plain_numeric_counts_as_attack() -> None:
    plain = EntryDTO(
        id=99, recorded_at=_d(2, 12), entry_date=date(2026, 10, 2),
        metric_type=MetricType.MIGRAINE, value_numeric=6.0,
        value_text=None, tags=None, extra=None,
    )
    s = compute_stats([plain], start=START, end=END, tz_name="UTC", now=NOW)
    assert s.attacks == 1 and s.headache_days == 1 and s.avg_peak == 6.0


def test_medication_flag_threshold() -> None:
    attacks = [
        _attack(datetime(2026, 9, 10 + i, 9, tzinfo=UTC), medication_text="x")
        for i in range(MEDICATION_DAYS_FLAG)
    ]
    s = compute_stats(attacks, start=START, end=END, tz_name="UTC", now=NOW)
    assert s.medication_days == MEDICATION_DAYS_FLAG
    assert s.medication_flag is True
    s2 = compute_stats(attacks[:-1], start=START, end=END, tz_name="UTC", now=NOW)
    assert s2.medication_flag is False


def test_to_dict_is_json_friendly() -> None:
    s = compute_stats([_attack(_d(1), medication_text="x", relief=5)],
                      start=START, end=END, tz_name="UTC", now=NOW)
    data = s.to_dict()
    json.dumps(data)
    assert data["attacks"] == 1
    assert data["medications"][0]["name"] == "x"



def test_duration_stats_say_how_many_attacks_they_cover() -> None:
    """avg/longest duration only cover attacks with a recorded end — the
    output must say so, or the model reports a duration for the others."""
    attacks = [
        _attack(_d(1), hours=4),
        _attack(_d(3), hours=None),  # ongoing
        _attack(_d(5), hours=None, status="ended", end_unknown=True),
    ]
    s = compute_stats(attacks, start=START, end=END, tz_name="UTC", now=NOW)
    assert s.attacks_with_known_duration == 1
    assert s.attacks_end_unknown == 1
    d = s.to_dict()
    assert d["attacks_with_known_duration"] == 1
