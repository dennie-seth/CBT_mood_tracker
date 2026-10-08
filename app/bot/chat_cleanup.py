"""Delete this chat's recent messages: /hide (everything the bot may still
delete, i.e. the last 48h) and auto-tidy (one note / thought-record span,
a few minutes after saving). Entries in the database are never touched.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import User
from app.infrastructure.repositories.chat_log_repo import RETENTION, SqlChatLogRepository
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository

log = structlog.get_logger(__name__)

TIDY_DELAY = timedelta(minutes=5)
_CHUNK = 100  # Telegram's deleteMessages limit
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_pending: set[asyncio.Task[None]] = set()


def configure(sm: async_sessionmaker[AsyncSession]) -> None:
    """Called once from main.py; auto-tidy runs after the request's own
    DB session is gone, so it needs its own sessionmaker."""
    global _sessionmaker
    _sessionmaker = sm


async def _delete(bot: Bot, chat_id: int, ids: list[int]) -> None:
    for i in range(0, len(ids), _CHUNK):
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=ids[i:i + _CHUNK])
        except TelegramAPIError as exc:  # too old / already gone — nothing to do
            log.info("chat_delete_failed", error_type=type(exc).__name__)


async def clear_chat(
    bot: Bot, sm: Callable[[], Any], *, chat_id: int, now: datetime
) -> int:
    async with sm() as session:
        repo = SqlChatLogRepository(session)
        ids = await repo.ids_since(chat_id, now - RETENTION)
        await _delete(bot, chat_id, ids)
        await repo.forget(chat_id, ids)
        await session.commit()
    log.info("chat_cleared", count=len(ids))
    return len(ids)


async def tidy_span(
    bot: Bot, sm: Callable[[], Any], *, chat_id: int, first_id: int, last_id: int,
    delay: float = TIDY_DELAY.total_seconds(),
) -> None:
    if delay:
        await asyncio.sleep(delay)
    async with sm() as session:
        repo = SqlChatLogRepository(session)
        ids = await repo.ids_between(chat_id, first_id, last_id)
        await _delete(bot, chat_id, ids)
        await repo.forget(chat_id, ids)
        await session.commit()
    log.info("chat_tidied", count=len(ids))


def _track(coro: Awaitable[None]) -> None:
    task = asyncio.ensure_future(coro)
    _pending.add(task)  # keep a reference until done
    task.add_done_callback(_pending.discard)


async def maybe_tidy(
    bot: Bot | None, session: AsyncSession, user: User, *,
    chat_id: int, first_id: int | None, last_id: int,
) -> None:
    """If the user turned on /tidy, delete [first_id, last_id] later.
    Best-effort: a restart before the delay simply skips it."""
    if bot is None or first_id is None or _sessionmaker is None:
        return
    if not await SqlScheduleRepository(session).tidy_enabled(user.id):
        return
    _track(tidy_span(bot, _sessionmaker, chat_id=chat_id, first_id=first_id, last_id=last_id))
