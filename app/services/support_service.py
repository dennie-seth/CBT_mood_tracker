"""'Things that helped you before' — the user's own words, no AI, no advice.

Sources: their coping entries (newest first) and behavioral-activation plans
they rated as helping a lot (actual_effect >= 7).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.domain.enums import MetricType
from app.services.entry_service import EntryService

LOOKBACK = timedelta(days=180)
HELPED_A_LOT = 7
MAX_COPING = 3
MAX_ACTIVITIES = 2


class SupportService:
    def __init__(self, entries: EntryService) -> None:
        self._entries = entries

    async def helped_before(self, user_id: int, *, today: date) -> list[str]:
        start = today - LOOKBACK
        seen: set[str] = set()
        out: list[str] = []

        def add(text: str, limit: int, counter: list[int]) -> None:
            key = " ".join(text.lower().split())
            if key and key not in seen and counter[0] < limit:
                seen.add(key)
                out.append(text.strip())
                counter[0] += 1

        coping = await self._entries.list_range(user_id, start, today, [MetricType.COPING])
        n = [0]
        for e in sorted(coping, key=lambda e: e.recorded_at, reverse=True):
            if e.value_text:
                add(e.value_text, MAX_COPING, n)

        plans = await self._entries.list_range(user_id, start, today, [MetricType.ACTIVITY_PLAN])
        helped = [
            p for p in plans
            if (p.extra or {}).get("status") == "done"
            and int((p.extra or {}).get("actual_effect") or 0) >= HELPED_A_LOT
        ]
        helped.sort(
            key=lambda p: (int((p.extra or {}).get("actual_effect") or 0), p.recorded_at),
            reverse=True,
        )
        n = [0]
        for p in helped:
            add(str((p.extra or {}).get("plan_text", "")), MAX_ACTIVITIES, n)
        return out
