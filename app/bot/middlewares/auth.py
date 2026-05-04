from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser

log = structlog.get_logger(__name__)

_GROUP_REFUSAL = (
    "This bot only works in a private chat — your tracked data must not be exposed "
    "to other group members. Please /start me in a direct chat instead."
)
_PRIVATE_REFUSAL = "This bot is private. Access denied."


class AllowlistMiddleware(BaseMiddleware):
    """Outermost auth gate.

    Two independent checks must pass for a handler to run:
    1. `event_from_user.id` is in the configured allowlist.
    2. The event happens in a 1:1 private chat — never a group/supergroup/channel.

    Why (2): every handler replies via `message.answer(...)` to the event's
    chat_id. If an allow-listed user invites the bot into a group, running
    /today, /ask, /export, etc. there would surface decrypted notes, thought
    records, charts and PDFs to all group members, including non-allow-listed
    ones. We refuse to operate outside private chats.
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
            return  # silently drop events without a user (channels, etc.)

        if tg_user.id not in self._allowed:
            log.warning("rejected_unauthorized", telegram_id=tg_user.id)
            await self._refuse(event, _PRIVATE_REFUSAL)
            return

        if not _is_private_chat(event):
            log.warning(
                "rejected_non_private_chat",
                telegram_id=tg_user.id,
                event_kind=type(event).__name__,
            )
            await self._refuse(event, _GROUP_REFUSAL)
            return

        return await handler(event, data)

    @staticmethod
    async def _refuse(event: TelegramObject, message: str) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception:  # never let a refusal failure mask the real reject
            pass


def _is_private_chat(event: TelegramObject) -> bool:
    """True iff the event originated from a 1:1 private chat with the bot."""
    chat = None
    if isinstance(event, Message):
        chat = event.chat
    elif isinstance(event, CallbackQuery) and event.message is not None:
        chat = event.message.chat
    if chat is None:
        # No chat attached (e.g. inline_query, business_message). Refuse — those
        # paths aren't part of this bot's surface today.
        return False
    return getattr(chat, "type", None) == "private"
