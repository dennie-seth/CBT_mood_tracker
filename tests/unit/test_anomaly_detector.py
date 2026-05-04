"""AnomalyDetector is a pure function over a daily-summary DataFrame.

Rules (v1 — heuristic, explainable, no statistical baselines):

- LOW_MOOD_STREAK : avg mood per day <= 4 on at least 3 consecutive
  days ending today (today must have a mood log to count).
- SLEEP_CRASH    : sleep_hours <= 5 on at least 2 consecutive days
  ending today.
- ANXIETY_SPIKE  : anxiety >= 8 on today.

The detector returns ALL triggered anomalies in priority order so the
caller can pick the highest signal one (or render multiple).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.services.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    AnomalyKind,
)


def _df(rows: dict[str, list[float | None]], dates: list[str]) -> pd.DataFrame:
    """Helper to build a daily-summary-shaped DataFrame from columnar input."""
    df = pd.DataFrame(rows, index=pd.to_datetime(dates))
    df.index.name = "entry_date"
    return df


# ---- LOW_MOOD_STREAK ---------------------------------------------------


def test_low_mood_streak_triggers_after_three_consecutive_low_days() -> None:
    df = _df(
        {"mood": [4.0, 3.0, 4.0]},
        ["2026-05-02", "2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    kinds = [a.kind for a in out]
    assert AnomalyKind.LOW_MOOD_STREAK in kinds
    a = next(x for x in out if x.kind == AnomalyKind.LOW_MOOD_STREAK)
    assert a.summary["values"] == [4.0, 3.0, 4.0]
    assert a.summary["days"] == 3


def test_low_mood_streak_does_not_trigger_with_only_two_low_days() -> None:
    df = _df(
        {"mood": [6.0, 3.0, 4.0]},
        ["2026-05-02", "2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert AnomalyKind.LOW_MOOD_STREAK not in [a.kind for a in out]


def test_low_mood_streak_requires_today_entry() -> None:
    """If the most recent low-mood day isn't today, no probe."""
    df = _df(
        {"mood": [3.0, 3.0, 3.0]},
        ["2026-05-01", "2026-05-02", "2026-05-03"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert AnomalyKind.LOW_MOOD_STREAK not in [a.kind for a in out]


# ---- SLEEP_CRASH -------------------------------------------------------


def test_sleep_crash_triggers_after_two_consecutive_short_nights() -> None:
    df = _df(
        {"sleep_hours": [4.5, 5.0]},
        ["2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    kinds = [a.kind for a in out]
    assert AnomalyKind.SLEEP_CRASH in kinds
    a = next(x for x in out if x.kind == AnomalyKind.SLEEP_CRASH)
    assert a.summary["values"] == [4.5, 5.0]


def test_sleep_crash_does_not_trigger_one_short_night() -> None:
    df = _df(
        {"sleep_hours": [7.0, 4.5]},
        ["2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert AnomalyKind.SLEEP_CRASH not in [a.kind for a in out]


# ---- ANXIETY_SPIKE -----------------------------------------------------


def test_anxiety_spike_triggers_at_threshold_today() -> None:
    df = _df({"anxiety": [4.0, 8.0]}, ["2026-05-03", "2026-05-04"])
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    kinds = [a.kind for a in out]
    assert AnomalyKind.ANXIETY_SPIKE in kinds
    a = next(x for x in out if x.kind == AnomalyKind.ANXIETY_SPIKE)
    assert a.summary["value"] == 8.0


def test_anxiety_spike_does_not_trigger_below_threshold() -> None:
    df = _df({"anxiety": [7.0]}, ["2026-05-04"])
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert AnomalyKind.ANXIETY_SPIKE not in [a.kind for a in out]


def test_anxiety_spike_only_uses_today_not_past_high_days() -> None:
    df = _df({"anxiety": [9.0, 5.0]}, ["2026-05-03", "2026-05-04"])
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert AnomalyKind.ANXIETY_SPIKE not in [a.kind for a in out]


# ---- empty / no-op cases ----------------------------------------------


def test_empty_df_returns_no_anomalies() -> None:
    out = AnomalyDetector().detect(pd.DataFrame(), today=date(2026, 5, 4))
    assert out == []


def test_df_without_relevant_columns_returns_no_anomalies() -> None:
    df = _df({"hunger": [5.0, 5.0, 5.0]},
             ["2026-05-02", "2026-05-03", "2026-05-04"])
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert out == []


def test_multiple_anomalies_can_be_returned_together() -> None:
    df = _df(
        {
            "mood": [3.0, 3.0, 3.0],
            "anxiety": [5.0, 5.0, 9.0],
        },
        ["2026-05-02", "2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    kinds = {a.kind for a in out}
    assert AnomalyKind.LOW_MOOD_STREAK in kinds
    assert AnomalyKind.ANXIETY_SPIKE in kinds


def test_detector_results_sorted_by_priority() -> None:
    """Priority: LOW_MOOD_STREAK > SLEEP_CRASH > ANXIETY_SPIKE.

    A streak says more than a single-day spike, so the caller probing
    "the one most-pressing thing" gets the streak first.
    """
    df = _df(
        {
            "mood": [3.0, 3.0, 3.0],
            "sleep_hours": [4.0, 4.0, 4.0],
            "anxiety": [5.0, 5.0, 9.0],
        },
        ["2026-05-02", "2026-05-03", "2026-05-04"],
    )
    out = AnomalyDetector().detect(df, today=date(2026, 5, 4))
    assert [a.kind for a in out] == [
        AnomalyKind.LOW_MOOD_STREAK,
        AnomalyKind.SLEEP_CRASH,
        AnomalyKind.ANXIETY_SPIKE,
    ]


def test_anomaly_dataclass_is_frozen() -> None:
    a = Anomaly(kind=AnomalyKind.ANXIETY_SPIKE, summary={"value": 8.0})
    with pytest.raises((AttributeError, TypeError)):
        a.summary = {}  # type: ignore[misc]
