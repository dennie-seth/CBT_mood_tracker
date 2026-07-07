from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.summary_models import WeeklySummary


class SqlWeeklySummaryRepository:
    """Persistence for weekly summaries.

    Deliberately crypto-agnostic: `add` takes and `latest` returns the raw
    `summary_text_encrypted` bytes. Encryption/decryption lives in the
    service layer (SummaryService) so the ciphertext never has to round-trip
    through a component that also knows the key.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        user_id: int,
        *,
        week_start: date,
        week_end: date,
        summary_text_encrypted: bytes,
    ) -> WeeklySummary:
        row = WeeklySummary(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            summary_text_encrypted=summary_text_encrypted,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def latest(self, user_id: int, *, limit: int) -> list[WeeklySummary]:
        """Return the user's most recent summaries, newest first (max `limit`)."""
        stmt = (
            select(WeeklySummary)
            .where(WeeklySummary.user_id == user_id)
            .order_by(WeeklySummary.created_at.desc(), WeeklySummary.id.desc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return list(result.all())
