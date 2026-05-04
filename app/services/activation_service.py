from __future__ import annotations

from datetime import date, datetime, timezone

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryDTO, EntryService


class ActivationService:
    """Behavioral Activation: small façade for plan listing + status updates.

    All persistence happens through `EntryService` so the encryption,
    AuthZ (user_id ownership) and length-cap chokepoints stay in one place.
    """

    LOOKBACK_DAYS = 30

    def __init__(self, entries: EntryService) -> None:
        self._entries = entries

    async def list_open_plans(
        self, user_id: int, *, on_or_before: date
    ) -> list[EntryDTO]:
        """Return scheduled BA plans whose `planned_for` is on/before the
        given date (typically today in user's tz)."""
        start = date.fromordinal(on_or_before.toordinal() - self.LOOKBACK_DAYS)
        rows = await self._entries.list_range(
            user_id, start, on_or_before, [MetricType.ACTIVITY_PLAN]
        )
        return [
            r for r in rows
            if (r.extra or {}).get("status") == "scheduled"
        ]

    async def mark_done(
        self, entry_id: int, user: User, *, actual_effect: int
    ) -> EntryDTO:
        plan = await self._load_plan(entry_id, user)
        new_extra = {
            **plan.extra,
            "status": "done",
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
            "actual_effect": actual_effect,
        }
        return await self._entries.update_extra(entry_id, user, new_extra)

    async def mark_skipped(
        self, entry_id: int, user: User, *, reason_text: str | None
    ) -> EntryDTO:
        plan = await self._load_plan(entry_id, user)
        new_extra = {
            **plan.extra,
            "status": "skipped",
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if reason_text:
            new_extra["skip_reason_text"] = reason_text
        return await self._entries.update_extra(entry_id, user, new_extra)

    async def _load_plan(self, entry_id: int, user: User) -> EntryDTO:
        plan = await self._entries.get_for_user(entry_id, user)
        if plan is None:
            raise LookupError(f"entry {entry_id} not found or not accessible")
        if plan.metric_type != MetricType.ACTIVITY_PLAN:
            raise ValueError(f"entry {entry_id} is not a behavioral activation plan")
        if plan.extra is None:
            raise ValueError(f"entry {entry_id} has no plan data")
        if plan.extra.get("status") != "scheduled":
            raise ValueError(
                f"entry {entry_id} is already {plan.extra.get('status')}"
            )
        return plan
