"""Record message ids (never content) of private chats for /hide and tidy.

Incoming: a dispatcher middleware on messages. Outgoing: a request
middleware on the bot session that records the Message Telegram returns.
Both use their own short transaction so tracking can't break a handler.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.methods.base import TelegramMethod, TelegramType
from aiogram.types import Message, TelegramObject

from app.infrastructure.repositories.chat_log_repo import SqlChatLogRepository

log = structlog.get_logger(__name__)


async def _record(sm: Callable[[], Any], message: Message) -> None:
    if getattr(message.chat, "type", None) != "private":
        return
    try:
        async with sm() as session:
            await SqlChatLogRepository(session).record(
                message.chat.id, message.message_id, at=datetime.now(tz=UTC)
            )
            await session.commit()
    except Exception as exc:  # tracking is best-effort
        log.warning("chat_log_record_failed", error_type=type(exc).__name__)


class IncomingChatLogMiddleware(BaseMiddleware):
    def __init__(self, sm: Callable[[], Any]) -> None:
        self._sm = sm

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            await _record(self._sm, event)
        return await handler(event, data)


class OutgoingChatLogMiddleware(BaseRequestMiddleware):
    def __init__(self, sm: Callable[[], Any]) -> None:
        self._sm = sm

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Any,
        method: TelegramMethod[TelegramType],
    ) -> Any:
        result = await make_request(bot, method)
        if isinstance(result, Message):
            await _record(self._sm, result)
        return result
