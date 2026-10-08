"""Gentle "is it over?" reminders for open migraine attacks.

Piggybacks SummaryScheduler's tick. For each allow-listed user:

  1. waking hours only (08:00 ≤ local < 22:00) — cheap, no DB
  2. open attacks (MigraineService.list_open)
  3. `reminder_due`: ≥4h since onset, ≥4h since the last reminder,
     at most 3 per attack, never after "Don't remind me"
  4. stamp, commit, then send the attack card with a mute button

Stamp BEFORE send (same rule as anomaly check-ins): a failed Telegram send
costs one reminder instead of re-sending every minute. Logs carry ids and
counts only.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any, Protocol

import pytz
import structlog
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.bot.migraine_card import cb, render_card
from app.domain.models import User
from app.services.migraine_service import MigraineService

log = structlog.get_logger(__name__)

_WAKING_START = time(8, 0)
_WAKING_END = time(22, 0)
FIRST_AFTER = timedelta(hours=4)
EVERY = timedelta(hours=4)
MAX_REMINDERS = 3


class _BotLike(Protocol):
    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Any: ...


def reminder_due(extra: dict[str, Any], now_utc: datetime) -> bool:
    """Pure rule for one attack's `extra`."""
    if extra.get("status") != "ongoing" or extra.get("reminders_muted"):
        return False
    if int(extra.get("reminder_count") or 0) >= MAX_REMINDERS:
        return False
    started = datetime.fromisoformat(extra["started_at"])
    if now_utc - started < FIRST_AFTER:
        return False
    last = extra.get("reminded_at")
    return last is None or now_utc - datetime.fromisoformat(last) >= EVERY


class MigraineReminderService:
    def __init__(
        self,
        *,
        sessionmaker: Callable[[], Any],
        migraine_factory: Callable[[Any, datetime], MigraineService],
        bot: _BotLike,
    ) -> None:
        self._sm = sessionmaker
        self._migraine_factory = migraine_factory
        self._bot = bot

    async def maybe_remind(self, user: User, *, now_utc: datetime) -> None:
        if now_utc.tzinfo is None:
            now_utc = pytz.utc.localize(now_utc)
        local = now_utc.astimezone(pytz.timezone(user.timezone))
        if not (_WAKING_START <= local.time() < _WAKING_END):
            return

        to_send = []
        async with self._sm() as session:
            svc = self._migraine_factory(session, now_utc)
            for attack in await svc.list_open(user.id, today=local.date()):
                if reminder_due(attack.extra or {}, now_utc):
                    to_send.append(await svc.mark_reminded(attack.id, user, at=now_utc))
            if to_send:
                await session.commit()

        for attack in to_send:
            text, kb = render_card(attack, user.language, user.timezone, now_utc)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                *kb.inline_keyboard,
                [InlineKeyboardButton(
                    text=t(user.language, "migraine.btn.mute"),
                    callback_data=cb("mute", attack.id),
                )],
            ])
            try:
                await self._bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"{t(user.language, 'migraine.reminder')}\n\n{text}",
                    reply_markup=kb,
                )
            except Exception as exc:
                log.warning("migraine_reminder_send_failed", user_id=user.id,
                            entry_id=attack.id, error_type=type(exc).__name__)
                continue
            log.info("migraine_reminder_sent", user_id=user.id, entry_id=attack.id,
                     count=(attack.extra or {}).get("reminder_count"))
