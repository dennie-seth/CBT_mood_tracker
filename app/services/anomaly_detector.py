"""Heuristic anomaly detection over the daily-summary DataFrame.

Pure: in -> DataFrame, today; out -> list[Anomaly]. No DB, no IO.

Rules are intentionally simple and explainable. Statistical baselines
(rolling mean ± Nσ) need 14+ days of consistent logging to be useful and
add complexity that hasn't paid for itself yet — re-evaluate if the
heuristic version starts producing too many false positives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

import pandas as pd


class AnomalyKind(StrEnum):
    LOW_MOOD_STREAK = "low_mood_streak"
    SLEEP_CRASH = "sleep_crash"
    ANXIETY_SPIKE = "anxiety_spike"


# Priority: long-running pattern beats single-day spike.
_PRIORITY: dict[AnomalyKind, int] = {
    AnomalyKind.LOW_MOOD_STREAK: 0,
    AnomalyKind.SLEEP_CRASH: 1,
    AnomalyKind.ANXIETY_SPIKE: 2,
}


@dataclass(frozen=True, slots=True)
class Anomaly:
    kind: AnomalyKind
    summary: dict[str, Any] = field(default_factory=dict)


class AnomalyDetector:
    LOW_MOOD_THRESHOLD: float = 4.0
    LOW_MOOD_STREAK_DAYS: int = 3
    SLEEP_CRASH_THRESHOLD: float = 5.0
    SLEEP_CRASH_STREAK_DAYS: int = 2
    ANXIETY_SPIKE_THRESHOLD: float = 8.0

    def detect(self, df: pd.DataFrame, *, today: date) -> list[Anomaly]:
        if df.empty:
            return []
        out: list[Anomaly] = []

        if (a := self._low_mood_streak(df, today)) is not None:
            out.append(a)
        if (a := self._sleep_crash(df, today)) is not None:
            out.append(a)
        if (a := self._anxiety_spike(df, today)) is not None:
            out.append(a)

        out.sort(key=lambda x: _PRIORITY[x.kind])
        return out

    # ----------------------------------------------------------------

    def _trailing_values(
        self, df: pd.DataFrame, col: str, today: date, n_days: int
    ) -> list[float] | None:
        """Return values for the last `n_days` ending today, or None if any
        of those days is missing in the index. Today's value is required —
        the streak must end on the day we're probing."""
        if col not in df.columns:
            return None
        ts = pd.Timestamp(today)
        try:
            today_val = df.loc[ts, col]
        except KeyError:
            return None
        if pd.isna(today_val):
            return None

        values: list[float] = [float(today_val)]
        for i in range(1, n_days):
            day = ts - pd.Timedelta(days=i)
            try:
                v = df.loc[day, col]
            except KeyError:
                return None
            if pd.isna(v):
                return None
            values.append(float(v))
        values.reverse()  # oldest -> newest
        return values

    def _low_mood_streak(self, df: pd.DataFrame, today: date) -> Anomaly | None:
        vals = self._trailing_values(df, "mood", today, self.LOW_MOOD_STREAK_DAYS)
        if vals is None:
            return None
        if not all(v <= self.LOW_MOOD_THRESHOLD for v in vals):
            return None
        return Anomaly(
            kind=AnomalyKind.LOW_MOOD_STREAK,
            summary={
                "values": vals,
                "days": self.LOW_MOOD_STREAK_DAYS,
                "since": (today - timedelta(days=self.LOW_MOOD_STREAK_DAYS - 1)).isoformat(),
            },
        )

    def _sleep_crash(self, df: pd.DataFrame, today: date) -> Anomaly | None:
        vals = self._trailing_values(
            df, "sleep_hours", today, self.SLEEP_CRASH_STREAK_DAYS
        )
        if vals is None:
            return None
        if not all(v <= self.SLEEP_CRASH_THRESHOLD for v in vals):
            return None
        return Anomaly(
            kind=AnomalyKind.SLEEP_CRASH,
            summary={
                "values": vals,
                "days": self.SLEEP_CRASH_STREAK_DAYS,
            },
        )

    def _anxiety_spike(self, df: pd.DataFrame, today: date) -> Anomaly | None:
        vals = self._trailing_values(df, "anxiety", today, 1)
        if vals is None:
            return None
        if vals[0] < self.ANXIETY_SPIKE_THRESHOLD:
            return None
        return Anomaly(
            kind=AnomalyKind.ANXIETY_SPIKE,
            summary={"value": vals[0]},
        )
