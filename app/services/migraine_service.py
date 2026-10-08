from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryDTO, EntryService
from app.services.migraine_stats import MigraineStats, compute_stats

# Stable keys stored in extra; labels live in i18n
# ("migraine.sym.<key>" / "migraine.trg.<key>").
SYMPTOMS: tuple[str, ...] = ("nausea", "light", "sound", "one_sided")
TRIGGERS: tuple[str, ...] = (
    "sleep", "stress", "skipped_meal", "dehydration",
    "alcohol", "screens", "weather", "cycle",
)

# Small tolerance so "now" from the bot and the service clock don't race.
_FUTURE_SLACK = timedelta(minutes=1)


class MigraineErrorCode(StrEnum):
    NOT_FOUND = "not_found"
    NOT_MIGRAINE = "not_migraine"
    ALREADY_ENDED = "already_ended"
    NOT_ENDED = "not_ended"
    END_BEFORE_START = "end_before_start"
    IN_FUTURE = "in_future"
    BAD_SCALE = "bad_scale"
    UNKNOWN_SYMPTOM = "unknown_symptom"
    UNKNOWN_TRIGGER = "unknown_trigger"
    RELIEF_WITHOUT_MEDICATION = "relief_without_medication"


class MigraineError(ValueError):
    """Expected, user-facing failure. `code` maps to an i18n key
    (`migraine.err.<code>`); the message is for logs/tests only."""

    def __init__(self, code: MigraineErrorCode, detail: str = "") -> None:
        super().__init__(f"{code.value}: {detail}" if detail else code.value)
        self.code = code


class _Unset:
    pass


UNSET: Final = _Unset()


def _scale(value: int) -> int:
    if not 1 <= value <= 10:
        raise MigraineError(MigraineErrorCode.BAD_SCALE, str(value))
    return value


def _keys(values: Iterable[str], allowed: tuple[str, ...], code: MigraineErrorCode) -> list[str]:
    out = list(values)
    unknown = [v for v in out if v not in allowed]
    if unknown:
        raise MigraineError(code, ", ".join(unknown))
    return out


def _set_text(extra: dict[str, Any], key: str, value: str | None) -> None:
    if value and value.strip():
        extra[key] = value.strip()
    else:
        extra.pop(key, None)


class MigraineService:
    """Lifecycle and editing of migraine attacks.

    One attack = one MIGRAINE entry. `value_numeric` is
    max(start_intensity, peak_intensity), so attacks chart as their peak;
    everything else lives in `extra`. Every detail is optional and editable
    while the attack is open and after it ended. All persistence goes through
    `EntryService`, so `*_text` fields are encrypted and ownership is enforced
    there.
    """

    LOOKBACK_DAYS = 30
    STALE_AFTER = timedelta(hours=72)

    def __init__(
        self,
        entries: EntryService,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
    ) -> None:
        self._entries = entries
        self._now = clock

    # --- create / close -----------------------------------------------------

    async def start(
        self,
        user: User,
        *,
        intensity: int,
        started_at: datetime | None = None,
        aura: bool | None = None,
        symptoms: Iterable[str] = (),
        triggers: Iterable[str] = (),
        medication_text: str | None = None,
        trigger_text: str | None = None,
    ) -> EntryDTO:
        _scale(intensity)
        started_at = started_at or self._now()
        self._not_future(started_at)
        extra: dict[str, Any] = {
            "status": "ongoing",
            "started_at": started_at.isoformat(),
            "start_intensity": intensity,
            "peak_intensity": intensity,
            "aura": aura,
            "symptoms": _keys(symptoms, SYMPTOMS, MigraineErrorCode.UNKNOWN_SYMPTOM),
            "triggers": _keys(triggers, TRIGGERS, MigraineErrorCode.UNKNOWN_TRIGGER),
        }
        _set_text(extra, "medication_text", medication_text)
        _set_text(extra, "trigger_text", trigger_text)
        # recorded_at = onset, so the attack is bucketed on the day it began.
        return await self._entries.create(
            user, MetricType.MIGRAINE,
            value_numeric=float(intensity), extra=extra, recorded_at=started_at,
        )

    async def end(
        self,
        entry_id: int,
        user: User,
        *,
        ended_at: datetime | None = None,
        peak: int | None = None,
    ) -> EntryDTO:
        attack = await self.get_ongoing(entry_id, user)
        extra = dict(attack.extra or {})
        extra["status"] = "ended"
        self._apply_end(extra, ended_at or self._now())
        if peak is not None:
            extra["peak_intensity"] = _scale(peak)
        return await self._save(entry_id, user, extra)

    async def close_unknown_end(self, entry_id: int, user: User) -> EntryDTO:
        """Close an attack whose end time the user doesn't remember."""
        attack = await self.get_ongoing(entry_id, user)
        extra = dict(attack.extra or {})
        extra["status"] = "ended"
        extra["end_unknown"] = True
        extra.pop("ended_at", None)
        extra.pop("duration_minutes", None)
        return await self._save(entry_id, user, extra)

    async def mark_reminded(self, entry_id: int, user: User, *, at: datetime) -> EntryDTO:
        """Stamp an "is it over?" reminder (before sending, for idempotency)."""
        attack = await self.get_ongoing(entry_id, user)
        extra = dict(attack.extra or {})
        extra["reminder_count"] = int(extra.get("reminder_count") or 0) + 1
        extra["reminded_at"] = at.isoformat()
        return await self._save(entry_id, user, extra)

    async def mute_reminders(self, entry_id: int, user: User) -> EntryDTO:
        attack = await self.get(entry_id, user)
        extra = dict(attack.extra or {})
        extra["reminders_muted"] = True
        return await self._save(entry_id, user, extra)

    async def delete(self, entry_id: int, user: User) -> None:
        await self.get(entry_id, user)
        await self._entries.delete_for_user(entry_id, user)

    # --- edit ---------------------------------------------------------------

    async def update(
        self,
        entry_id: int,
        user: User,
        *,
        started_at: datetime | _Unset = UNSET,
        ended_at: datetime | _Unset = UNSET,
        intensity: int | _Unset = UNSET,
        peak: int | _Unset = UNSET,
        aura: bool | None | _Unset = UNSET,
        symptoms: Iterable[str] | _Unset = UNSET,
        triggers: Iterable[str] | _Unset = UNSET,
        medication_text: str | None | _Unset = UNSET,
        trigger_text: str | None | _Unset = UNSET,
        relief: int | _Unset = UNSET,
    ) -> EntryDTO:
        """Change any subset of an attack's details, open or ended."""
        attack = await self.get(entry_id, user)
        extra = dict(attack.extra or {})
        ended = extra.get("status") == "ended"
        new_start: datetime | None = None

        if not isinstance(intensity, _Unset):
            extra["start_intensity"] = _scale(intensity)
        if not isinstance(peak, _Unset):
            extra["peak_intensity"] = _scale(peak)
        if not isinstance(aura, _Unset):
            extra["aura"] = aura
        if not isinstance(symptoms, _Unset):
            extra["symptoms"] = _keys(symptoms, SYMPTOMS, MigraineErrorCode.UNKNOWN_SYMPTOM)
        if not isinstance(triggers, _Unset):
            extra["triggers"] = _keys(triggers, TRIGGERS, MigraineErrorCode.UNKNOWN_TRIGGER)
        if not isinstance(trigger_text, _Unset):
            _set_text(extra, "trigger_text", trigger_text)
        if not isinstance(medication_text, _Unset):
            _set_text(extra, "medication_text", medication_text)
            if "medication_text" not in extra:
                extra.pop("relief", None)
        if not isinstance(relief, _Unset):
            if not extra.get("medication_text"):
                raise MigraineError(MigraineErrorCode.RELIEF_WITHOUT_MEDICATION)
            extra["relief"] = _scale(relief)

        if not isinstance(started_at, _Unset):
            self._not_future(started_at)
            extra["started_at"] = started_at.isoformat()
            new_start = started_at
        if not isinstance(ended_at, _Unset):
            if not ended:
                raise MigraineError(MigraineErrorCode.NOT_ENDED)
            extra.pop("end_unknown", None)
            self._apply_end(extra, ended_at)
        elif new_start is not None and extra.get("ended_at"):
            # Onset moved: re-validate and recompute against the known end.
            self._apply_end(extra, datetime.fromisoformat(extra["ended_at"]))

        return await self._save(entry_id, user, extra, recorded_at=new_start)

    # --- read ---------------------------------------------------------------

    async def get(self, entry_id: int, user: User) -> EntryDTO:
        attack = await self._entries.get_for_user(entry_id, user)
        if attack is None:
            raise MigraineError(MigraineErrorCode.NOT_FOUND, str(entry_id))
        if attack.metric_type != MetricType.MIGRAINE:
            raise MigraineError(MigraineErrorCode.NOT_MIGRAINE, str(entry_id))
        return attack

    async def get_ongoing(self, entry_id: int, user: User) -> EntryDTO:
        attack = await self.get(entry_id, user)
        if (attack.extra or {}).get("status") != "ongoing":
            raise MigraineError(MigraineErrorCode.ALREADY_ENDED, str(entry_id))
        return attack

    async def list_open(self, user_id: int, *, today: date) -> list[EntryDTO]:
        """Every open attack in the lookback window, oldest first."""
        return [
            r for r in await self._recent(user_id, today)
            if (r.extra or {}).get("status") == "ongoing"
        ]

    async def latest(self, user_id: int, *, today: date) -> EntryDTO | None:
        """Most recent attack logged via /migraine (open or ended)."""
        rows = [r for r in await self._recent(user_id, today) if (r.extra or {}).get("status")]
        return rows[-1] if rows else None

    async def stats(
        self, user_id: int, *, start: date, end: date, tz_name: str
    ) -> MigraineStats:
        rows = await self._entries.list_range(user_id, start, end, [MetricType.MIGRAINE])
        return compute_stats(rows, start=start, end=end, tz_name=tz_name, now=self._now())

    async def first_attack_date(self, user_id: int, *, today: date) -> date | None:
        rows = await self._entries.list_range(
            user_id, date(1970, 1, 1), today, [MetricType.MIGRAINE]
        )
        return min((r.entry_date for r in rows), default=None)

    def is_stale(self, attack: EntryDTO) -> bool:
        """Open for so long (>72h) it was most likely forgotten."""
        started = datetime.fromisoformat((attack.extra or {})["started_at"])
        return self._now() - started > self.STALE_AFTER

    async def recent_medications(
        self, user_id: int, *, today: date, limit: int = 4
    ) -> list[str]:
        """Distinct medication texts from recent attacks, newest first
        (case-insensitive de-dup keeps the newest spelling)."""
        start = date.fromordinal(today.toordinal() - 90)
        rows = await self._entries.list_range(user_id, start, today, [MetricType.MIGRAINE])
        seen: set[str] = set()
        out: list[str] = []
        for r in reversed(rows):
            med = (r.extra or {}).get("medication_text")
            if isinstance(med, str) and med.lower() not in seen:
                seen.add(med.lower())
                out.append(med)
                if len(out) == limit:
                    break
        return out

    # --- internals ----------------------------------------------------------

    async def _recent(self, user_id: int, today: date) -> list[EntryDTO]:
        start = date.fromordinal(today.toordinal() - self.LOOKBACK_DAYS)
        return await self._entries.list_range(user_id, start, today, [MetricType.MIGRAINE])

    def _not_future(self, moment: datetime) -> None:
        if moment > self._now() + _FUTURE_SLACK:
            raise MigraineError(MigraineErrorCode.IN_FUTURE, moment.isoformat())

    def _apply_end(self, extra: dict[str, Any], ended_at: datetime) -> None:
        started_at = datetime.fromisoformat(extra["started_at"])
        self._not_future(ended_at)
        if ended_at < started_at:
            raise MigraineError(MigraineErrorCode.END_BEFORE_START)
        extra["ended_at"] = ended_at.isoformat()
        extra["duration_minutes"] = int((ended_at - started_at).total_seconds() // 60)

    async def _save(
        self,
        entry_id: int,
        user: User,
        extra: dict[str, Any],
        *,
        recorded_at: datetime | None = None,
    ) -> EntryDTO:
        start = int(extra.get("start_intensity") or extra.get("peak_intensity") or 1)
        peak = int(extra.get("peak_intensity") or start)
        extra["peak_intensity"] = max(start, peak)
        return await self._entries.update_extra(
            entry_id, user, extra,
            value_numeric=float(extra["peak_intensity"]),
            recorded_at=recorded_at,
        )
