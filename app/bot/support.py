"""Gentle support after a hard reading: the user's own "what helped" list
plus a breathing / grounding exercise. At most once every 2 hours, so
several readings in a rough spell don't repeat it. In-memory cooldown —
a restart just means it may show once more.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.i18n import t
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryService
from app.services.support_service import SupportService
from app.services.time import today_in_tz

COOLDOWN = timedelta(hours=2)
_last_offer: dict[int, datetime] = {}


def reset_cooldowns() -> None:
    _last_offer.clear()


def is_very_hard(metric: MetricType, value: float) -> bool:
    return (metric in (MetricType.ANXIETY, MetricType.STRESS) and value >= 8) or (
        metric is MetricType.MOOD and value <= 3
    )


def exercises_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "support.btn.breathe"), callback_data="br:box")],
        [InlineKeyboardButton(text=t(lang, "support.btn.ground"), callback_data="br:ground")],
    ])


async def offer_support(
    message: Message,
    user: User,
    entries: EntryService,
    readings: Sequence[tuple[MetricType, float]],
) -> None:
    if not any(is_very_hard(m, v) for m, v in readings):
        return
    now = datetime.now(tz=UTC)
    last = _last_offer.get(user.id)
    if last is not None and now - last < COOLDOWN:
        return
    _last_offer[user.id] = now

    lang = user.language
    helped = await SupportService(entries).helped_before(
        user.id, today=today_in_tz(user.timezone)
    )
    parts = []
    if helped:
        parts.append(t(lang, "support.header"))
        parts.extend(f"• {h}" for h in helped)
        parts.append("")
    parts.append(t(lang, "support.offer"))
    await message.answer("\n".join(parts), reply_markup=exercises_keyboard(lang))
