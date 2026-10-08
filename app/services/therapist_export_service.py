"""Composes a clinician-ready report payload.

Pulls the same daily numeric summary `/export` already builds, plus the
free-text slices a therapist actually reads in session: thought records,
behavioral activation outcomes, journal notes, and other free-text
metrics (symptoms, triggers, coping, etc.).

Decryption happens here (via EntryService) so PdfService never touches
FernetCipher and stays a pure renderer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pandas as pd
import pytz

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.analysis_service import AnalysisService
from app.services.entry_service import EntryDTO, EntryService
from app.services.migraine_stats import MigraineStats, compute_stats

_FREE_TEXT_OTHER: list[MetricType] = [
    MetricType.SYMPTOM,
    MetricType.ACTIVITY,
    MetricType.SUBSTANCE,
    MetricType.TRIGGER,
    MetricType.COPING,
]


@dataclass(frozen=True, slots=True)
class ThoughtRecord:
    entry_date: date
    situation: str
    automatic_thought: str
    distortion: str
    reframe: str


@dataclass(frozen=True, slots=True)
class BAOutcome:
    entry_date: date
    plan_text: str
    status: str
    predicted_effect: int | None
    actual_effect: int | None
    skip_reason: str | None


@dataclass(frozen=True, slots=True)
class TextEntry:
    entry_date: date
    metric_type: MetricType
    text: str


@dataclass(frozen=True, slots=True)
class MigraineDiaryRow:
    entry_date: date
    start_time: str  # HH:MM in the user's tz
    duration_minutes: int | None
    status: str  # ended | ongoing | end_unknown | number_only
    peak: int
    aura: bool | None
    symptoms: list[str]
    triggers: list[str]
    trigger_text: str | None
    medication: str | None
    relief: int | None


@dataclass(frozen=True, slots=True)
class TherapistReportData:
    daily_df: pd.DataFrame
    thought_records: list[ThoughtRecord] = field(default_factory=list)
    ba_outcomes: list[BAOutcome] = field(default_factory=list)
    notes: list[TextEntry] = field(default_factory=list)
    other_text: list[TextEntry] = field(default_factory=list)
    migraines: list[MigraineDiaryRow] = field(default_factory=list)
    migraine_stats: MigraineStats | None = None


class TherapistExportService:
    def __init__(self, entry_service: EntryService) -> None:
        self._es = entry_service
        self._analysis = AnalysisService(entry_service._repo)  # type: ignore[attr-defined]

    async def collect(
        self, user: User, *, start: date, end: date
    ) -> TherapistReportData:
        daily_df = await self._analysis.daily_summary(user.id, start, end)

        thoughts = await self._es.list_range(
            user.id, start, end, [MetricType.THOUGHT_RECORD]
        )
        thought_records = [
            ThoughtRecord(
                entry_date=t.entry_date,
                situation=(t.extra or {}).get("situation_text", "") or "",
                automatic_thought=(t.extra or {}).get("automatic_thought_text", "") or "",
                distortion=(t.extra or {}).get("distortion_text", "") or "",
                reframe=(t.extra or {}).get("reframe_text", "") or "",
            )
            for t in thoughts
        ]
        thought_records.sort(key=lambda r: r.entry_date)

        plans = await self._es.list_range(
            user.id, start, end, [MetricType.ACTIVITY_PLAN]
        )
        ba_outcomes = []
        for p in plans:
            extra = p.extra or {}
            ba_outcomes.append(
                BAOutcome(
                    entry_date=p.entry_date,
                    plan_text=extra.get("plan_text", "") or "",
                    status=extra.get("status", "scheduled"),
                    predicted_effect=extra.get("predicted_effect"),
                    actual_effect=extra.get("actual_effect"),
                    skip_reason=extra.get("skip_reason_text"),
                )
            )
        ba_outcomes.sort(key=lambda o: o.entry_date)

        note_entries = await self._es.list_range(user.id, start, end, [MetricType.NOTE])
        notes = [
            TextEntry(entry_date=n.entry_date, metric_type=MetricType.NOTE, text=n.value_text or "")
            for n in note_entries
            if n.value_text
        ]
        notes.sort(key=lambda n: n.entry_date)

        other = await self._es.list_range(user.id, start, end, _FREE_TEXT_OTHER)
        other_text = [
            TextEntry(
                entry_date=o.entry_date,
                metric_type=o.metric_type,
                text=o.value_text or "",
            )
            for o in other
            if o.value_text
        ]
        other_text.sort(key=lambda o: (o.entry_date, o.metric_type.value))

        attacks = await self._es.list_range(user.id, start, end, [MetricType.MIGRAINE])
        tz = pytz.timezone(user.timezone)
        migraines = [_diary_row(a, tz) for a in attacks]
        migraines.sort(key=lambda r: (r.entry_date, r.start_time))
        migraine_stats = (
            compute_stats(
                attacks, start=start, end=end, tz_name=user.timezone,
                now=datetime.now(tz=UTC),
            )
            if attacks
            else None
        )

        return TherapistReportData(
            daily_df=daily_df,
            thought_records=thought_records,
            ba_outcomes=ba_outcomes,
            notes=notes,
            other_text=other_text,
            migraines=migraines,
            migraine_stats=migraine_stats,
        )


def _diary_row(a: EntryDTO, tz: pytz.BaseTzInfo) -> MigraineDiaryRow:
    x = a.extra or {}
    onset = datetime.fromisoformat(x["started_at"]) if x.get("started_at") else a.recorded_at
    if not x:
        status = "number_only"
    elif x.get("status") == "ongoing":
        status = "ongoing"
    elif x.get("end_unknown"):
        status = "end_unknown"
    else:
        status = "ended"
    start_int = int(x.get("start_intensity") or 0)
    peak = max(start_int, int(x.get("peak_intensity") or start_int)) if x else int(a.value_numeric or 0)
    return MigraineDiaryRow(
        entry_date=a.entry_date,
        start_time=onset.astimezone(tz).strftime("%H:%M"),
        duration_minutes=x.get("duration_minutes"),
        status=status,
        peak=peak,
        aura=x.get("aura"),
        symptoms=list(x.get("symptoms") or []),
        triggers=list(x.get("triggers") or []),
        trigger_text=x.get("trigger_text"),
        medication=x.get("medication_text"),
        relief=x.get("relief"),
    )
