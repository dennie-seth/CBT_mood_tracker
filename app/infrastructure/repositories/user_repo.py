from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self, telegram_id: int, display_name: str | None, timezone: str
    ) -> User:
        user = User(telegram_id=telegram_id, display_name=display_name, timezone=timezone)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_timezone(self, user_id: int, timezone: str) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(timezone=timezone)
        )
