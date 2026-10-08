from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryDTO, EntryService

# Stable keys stored in extra["symptoms"]; labels live in i18n
# ("migraine.sym.<key>").
SYMPTOMS: tuple[str, ...] = ("nausea", "light", "sound", "one_sided")


def _check_intensity(name: str, value: int) -> None:
    if not 1 <= value <= 10:
        raise ValueError(f"{name} must be 1-10, got {value}")


class MigraineService:
    """Start/end lifecycle for migraine attacks.

    One attack = one MIGRAINE entry. `value_numeric` is the peak intensity
    (so attacks show up in charts and daily_summary); everything else lives
    in `extra`. All persistence goes through `EntryService`, so `*_text`
    fields are encrypted and ownership is enforced there.
    """

    LOOKBACK_DAYS = 7

    def __init__(self, entries: EntryService) -> None:
        self._entries = entries

    async def start(
        self,
        user: User,
        *,
        started_at: datetime,
        intensity: int,
        aura: bool,
        symptoms: list[str],
        medication_text: str | None,
        trigger_text: str | None,
    ) -> EntryDTO:
        _check_intensity("intensity", intensity)
        unknown = [s for s in symptoms if s not in SYMPTOMS]
        if unknown:
            raise ValueError(f"unknown symptoms: {unknown}")

        extra: dict[str, Any] = {
            "status": "ongoing",
            "started_at": started_at.isoformat(),
            "start_intensity": intensity,
            "aura": aura,
            "symptoms": list(symptoms),
        }
        if medication_text and medication_text.strip():
            extra["medication_text"] = medication_text.strip()
        if trigger_text and trigger_text.strip():
            extra["trigger_text"] = trigger_text.strip()

        # recorded_at = onset, so the attack is bucketed on the day it began.
        return await self._entries.create(
            user,
            MetricType.MIGRAINE,
            value_numeric=float(intensity),
            extra=extra,
            recorded_at=started_at,
        )

    async def list_ongoing(
        self, user_id: int, *, on_or_before: date
    ) -> list[EntryDTO]:
        start = date.fromordinal(on_or_before.toordinal() - self.LOOKBACK_DAYS)
        rows = await self._entries.list_range(
            user_id, start, on_or_before, [MetricType.MIGRAINE]
        )
        return [r for r in rows if (r.extra or {}).get("status") == "ongoing"]

    async def end(
        self,
        entry_id: int,
        user: User,
        *,
        ended_at: datetime,
        peak_intensity: int,
        relief: int | None = None,
        medication_text: str | None = None,
    ) -> EntryDTO:
        _check_intensity("peak_intensity", peak_intensity)
        attack = await self.get_ongoing(entry_id, user)
        extra = dict(attack.extra or {})

        started_at = datetime.fromisoformat(extra["started_at"])
        if ended_at < started_at:
            raise ValueError("attack can't end before it started")

        if medication_text and medication_text.strip():
            extra["medication_text"] = medication_text.strip()
        if relief is not None:
            if not extra.get("medication_text"):
                raise ValueError("relief needs a medication to rate")
            _check_intensity("relief", relief)
            extra["relief"] = relief

        extra["status"] = "ended"
        extra["ended_at"] = ended_at.isoformat()
        extra["duration_minutes"] = int((ended_at - started_at).total_seconds() // 60)

        peak = max(peak_intensity, int(extra.get("start_intensity", peak_intensity)))
        return await self._entries.update_extra(
            entry_id, user, extra, value_numeric=float(peak)
        )

    async def get_ongoing(self, entry_id: int, user: User) -> EntryDTO:
        attack = await self._entries.get_for_user(entry_id, user)
        if attack is None:
            raise LookupError(f"entry {entry_id} not found or not accessible")
        if attack.metric_type != MetricType.MIGRAINE:
            raise ValueError(f"entry {entry_id} is not a migraine attack")
        status = (attack.extra or {}).get("status")
        if status != "ongoing":
            raise ValueError(f"entry {entry_id} is already {status or 'closed'}")
        return attack
