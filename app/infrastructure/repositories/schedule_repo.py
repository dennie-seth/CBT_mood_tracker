from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.models import User
from app.infrastructure.schedule_models import SchedulePrefs


class SqlScheduleRepository:
    """CRUD over schedule_prefs.

    `set_daily` / `set_weekly` upsert just the relevant half so callers
    can change one schedule without clobbering the other.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> SchedulePrefs | None:
        return await self._session.scalar(
            select(SchedulePrefs).where(SchedulePrefs.user_id == user_id)
        )

    async def list_enabled(self) -> list[tuple[SchedulePrefs, User]]:
        """Return (prefs, user) pairs for users with daily OR weekly enabled.

        The joined User is eager-loaded so dispatch code can read
        `.timezone` / `.telegram_id` without a lazy-load round trip.
        """
        stmt = (
            select(SchedulePrefs, User)
            .join(User, User.id == SchedulePrefs.user_id)
            .where(
                (SchedulePrefs.daily_enabled.is_(True))
                | (SchedulePrefs.weekly_enabled.is_(True))
            )
        )
        result = await self._session.execute(stmt)
        return [(p, u) for p, u in result.all()]

    async def set_daily(
        self,
        user_id: int,
        *,
        enabled: bool,
        at: time | None = None,
    ) -> SchedulePrefs:
        prefs = await self._get_or_create(user_id)
        prefs.daily_enabled = enabled
        if at is not None:
            prefs.daily_at = at
        if not enabled:
            # Forget the dedup stamp so re-enabling later doesn't suppress today's send.
            prefs.daily_last_sent_date = None
        prefs.updated_at = datetime.now(tz=timezone.utc)
        return prefs

    async def set_weekly(
        self,
        user_id: int,
        *,
        enabled: bool,
        weekday: int | None = None,
        at: time | None = None,
    ) -> SchedulePrefs:
        prefs = await self._get_or_create(user_id)
        prefs.weekly_enabled = enabled
        if weekday is not None:
            prefs.weekly_weekday = weekday
        if at is not None:
            prefs.weekly_at = at
        if not enabled:
            prefs.weekly_last_sent_date = None
        prefs.updated_at = datetime.now(tz=timezone.utc)
        return prefs

    async def stamp_daily_sent(self, user_id: int, *, on: date) -> None:
        prefs = await self._get_or_create(user_id)
        prefs.daily_last_sent_date = on
        prefs.updated_at = datetime.now(tz=timezone.utc)

    async def stamp_weekly_sent(self, user_id: int, *, on: date) -> None:
        prefs = await self._get_or_create(user_id)
        prefs.weekly_last_sent_date = on
        prefs.updated_at = datetime.now(tz=timezone.utc)

    async def _get_or_create(self, user_id: int) -> SchedulePrefs:
        prefs = await self.get(user_id)
        if prefs is None:
            prefs = SchedulePrefs(user_id=user_id)
            self._session.add(prefs)
            await self._session.flush()
        return prefs
