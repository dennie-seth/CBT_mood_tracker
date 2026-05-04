from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Entry


class SqlEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: Entry) -> Entry:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_range(
        self,
        user_id: int,
        start: date,
        end: date,
        metric_types: list[str] | None = None,
    ) -> list[Entry]:
        stmt = (
            select(Entry)
            .where(Entry.user_id == user_id)
            .where(Entry.entry_date >= start)
            .where(Entry.entry_date <= end)
            .order_by(Entry.recorded_at.asc())
        )
        if metric_types:
            stmt = stmt.where(Entry.metric_type.in_(metric_types))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_user(self, entry_id: int, user_id: int) -> Entry | None:
        return await self._session.scalar(
            select(Entry).where(Entry.id == entry_id, Entry.user_id == user_id)
        )

    async def exists(self, entry_id: int) -> bool:
        return (
            await self._session.scalar(
                select(Entry.id).where(Entry.id == entry_id)
            )
        ) is not None

    async def daily_aggregates(
        self,
        user_id: int,
        start: date,
        end: date,
    ) -> list[tuple[date, str, Decimal | None, int]]:
        stmt = (
            select(
                Entry.entry_date,
                Entry.metric_type,
                func.avg(Entry.value_numeric).label("avg_numeric"),
                func.count(Entry.id).label("cnt"),
            )
            .where(Entry.user_id == user_id)
            .where(Entry.entry_date >= start)
            .where(Entry.entry_date <= end)
            .group_by(Entry.entry_date, Entry.metric_type)
            .order_by(Entry.entry_date.asc(), Entry.metric_type.asc())
        )
        result = await self._session.execute(stmt)
        return [(d, m, a, c) for d, m, a, c in result.all()]
