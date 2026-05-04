from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.infrastructure.repositories.user_repo import SqlUserRepository

log = structlog.get_logger(__name__)


class UserContextMiddleware(BaseMiddleware):
    """Resolves or creates the domain User for the authenticated Telegram user.

    Must run AFTER AllowlistMiddleware and AFTER DbSessionMiddleware. Stores
    the User row under data["user"].
    """

    def __init__(self, settings: Settings) -> None:
        self._default_tz = settings.default_timezone

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")
        if tg_user is None or session is None:
            return await handler(event, data)

        repo = SqlUserRepository(session)
        user = await repo.get_by_telegram_id(tg_user.id)
        if user is None:
            display = (tg_user.full_name or tg_user.username or str(tg_user.id))[:120]
            user = await repo.create(tg_user.id, display, self._default_tz)
            log.info("user_registered", telegram_id=tg_user.id, user_id=user.id)

        data["user"] = user
        return await handler(event, data)
