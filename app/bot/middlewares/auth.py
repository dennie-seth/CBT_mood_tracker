from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

log = structlog.get_logger(__name__)


class AllowlistMiddleware(BaseMiddleware):
    """Outermost middleware: drops updates from non-allowlisted Telegram users.

    Rejected users get a generic refusal message; we audit the attempt by
    telegram_id only (no message content) so the operator can spot abuse.
    """

    def __init__(self, allowed_ids: frozenset[int]) -> None:
        self._allowed = allowed_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return  # silently drop updates without a user (channels, etc.)

        if tg_user.id not in self._allowed:
            log.warning("rejected_unauthorized", telegram_id=tg_user.id)
            # Soft refusal — better than silent drop because the legit user
            # mistyping a 2nd-account chat would be confused.
            try:
                from aiogram.types import Message

                if isinstance(event, Message):
                    await event.answer("This bot is private. Access denied.")
            except Exception:
                pass
            return

        return await handler(event, data)
