from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuditLog


class SqlAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AuditLog) -> None:
        self._session.add(entry)
        await self._session.flush()
