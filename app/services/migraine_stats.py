"""Pure summary of migraine attacks — shared by /migraines, the
`migraine_stats` AI tool and the therapist PDF so they never disagree.

No IO, no decryption: takes already-decrypted EntryDTOs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pytz

from app.services.entry_service import EntryDTO

# Acute medication on this many days in ~a month is the commonly cited
# threshold where medication-overuse headache becomes a concern (lower
# bound — triptans; simple analgesics ≈15). Used only to suggest talking
# to a doctor, never to advise on dosing.
MEDICATION_DAYS_FLAG = 10


@dataclass(frozen=True, slots=True)
class MedicationStat:
    name: str
    attacks: int
    avg_relief: float | None
    rated: int


@dataclass(frozen=True, slots=True)
class MigraineStats:
    start: date
    end: date
    attacks: int = 0
    open_attacks: int = 0
    headache_days: int = 0
    # Durations only cover attacks with a recorded end — say how many.
    attacks_with_known_duration: int = 0
    attacks_end_unknown: int = 0
    avg_duration_minutes: int | None = None
    longest_minutes: int | None = None
    avg_peak: float | None = None
    max_peak: int | None = None
    aura: int = 0
    symptoms: dict[str, int] = field(default_factory=dict)  # most common first
    triggers: dict[str, int] = field(default_factory=dict)  # most common first
    medication_days: int = 0
    medications: list[MedicationStat] = field(default_factory=list)

    @property
    def medication_flag(self) -> bool:
        """Meaningful for a ~30-day window (callers compute one for that)."""
        return self.medication_days >= MEDICATION_DAYS_FLAG

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


def _peak(a: EntryDTO) -> int:
    x = a.extra or {}
    if x:
        start = int(x.get("start_intensity") or 0)
        return max(start, int(x.get("peak_intensity") or start))
    return int(a.value_numeric or 0)


def _days_covered(
    a: EntryDTO, tz: pytz.BaseTzInfo, now: datetime, start: date, end: date
) -> set[date]:
    x = a.extra or {}
    onset = datetime.fromisoformat(x["started_at"]) if x.get("started_at") else a.recorded_at
    first = onset.astimezone(tz).date()
    if x.get("ended_at"):
        last = datetime.fromisoformat(x["ended_at"]).astimezone(tz).date()
    elif x.get("status") == "ongoing":
        last = now.astimezone(tz).date()
    else:
        last = first
    days = {first + timedelta(days=i) for i in range((last - first).days + 1)}
    return {d for d in days if start <= d <= end}


def compute_stats(
    attacks: list[EntryDTO], *, start: date, end: date, tz_name: str, now: datetime
) -> MigraineStats:
    if not attacks:
        return MigraineStats(start=start, end=end)
    tz = pytz.timezone(tz_name)

    covered: set[date] = set()
    med_days: set[date] = set()
    durations: list[int] = []
    peaks: list[int] = []
    symptoms: Counter[str] = Counter()
    triggers: Counter[str] = Counter()
    meds: dict[str, dict[str, Any]] = {}
    open_attacks = aura = end_unknown = 0

    for a in sorted(attacks, key=lambda e: e.recorded_at):
        x = a.extra or {}
        covered |= _days_covered(a, tz, now, start, end)
        peaks.append(_peak(a))
        open_attacks += x.get("status") == "ongoing"
        aura += x.get("aura") is True
        end_unknown += bool(x.get("end_unknown"))
        if x.get("duration_minutes") is not None:
            durations.append(int(x["duration_minutes"]))
        symptoms.update(x.get("symptoms") or [])
        triggers.update(x.get("triggers") or [])
        med = x.get("medication_text")
        if isinstance(med, str) and med:
            med_days.add(a.entry_date)
            m = meds.setdefault(med.lower(), {"name": med, "attacks": 0, "reliefs": []})
            m["name"] = med  # newest spelling wins
            m["attacks"] += 1
            if x.get("relief") is not None:
                m["reliefs"].append(int(x["relief"]))

    return MigraineStats(
        start=start,
        end=end,
        attacks=len(attacks),
        open_attacks=open_attacks,
        headache_days=len(covered),
        attacks_with_known_duration=len(durations),
        attacks_end_unknown=end_unknown,
        avg_duration_minutes=round(sum(durations) / len(durations)) if durations else None,
        longest_minutes=max(durations) if durations else None,
        avg_peak=round(sum(peaks) / len(peaks), 1) if peaks else None,
        max_peak=max(peaks) if peaks else None,
        aura=aura,
        symptoms=dict(symptoms.most_common()),
        triggers=dict(triggers.most_common()),
        medication_days=len(med_days),
        medications=[
            MedicationStat(
                name=m["name"],
                attacks=m["attacks"],
                avg_relief=round(sum(m["reliefs"]) / len(m["reliefs"]), 1) if m["reliefs"] else None,
                rated=len(m["reliefs"]),
            )
            for m in sorted(meds.values(), key=lambda m: -m["attacks"])
        ],
    )
