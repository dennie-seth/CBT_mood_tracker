"""/hide (clear this chat), /tidy (auto-clear notes & thoughts), /pause
(quiet mode for every proactive message). None of these touch saved entries.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.chat_cleanup import clear_chat
from app.bot.i18n import t
from app.bot.migraine_card import fmt_when
from app.di import Container
from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository

router = Router()

MAX_PAUSE_DAYS = 14
_PAUSE_RE = re.compile(r"^(\d{1,2})\s*(d|д|days?|дн\w*)?$", re.IGNORECASE)
_RESUME_WORDS = {"off", "resume", "stop", "выкл", "стоп"}


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


# --- /hide -------------------------------------------------------------------

@router.message(Command("hide"))
async def cmd_hide(message: Message, user: User) -> None:
    lang = user.language
    await message.answer(
        t(lang, "hide.confirm"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            _btn(t(lang, "hide.btn.yes"), "hide:yes"),
            _btn(t(lang, "hide.btn.no"), "hide:no"),
        ]]),
    )


@router.callback_query(F.data.startswith("hide:"))
async def on_hide(cb: CallbackQuery, user: User, container: Container) -> None:
    lang = user.language
    msg = cb.message if isinstance(cb.message, Message) else None
    if cb.data != "hide:yes" or msg is None or cb.bot is None:
        if msg:
            await msg.edit_text(t(lang, "hide.cancelled"))
        await cb.answer()
        return
    await cb.answer()
    await clear_chat(cb.bot, container.sessionmaker, chat_id=msg.chat.id, now=datetime.now(tz=UTC))
    await msg.answer(t(lang, "hide.done"))


# --- /pause ------------------------------------------------------------------

def _pause_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(t(lang, f"pause.btn.{d}"), f"pause:{d}") for d in (1, 3, 7)],
        [_btn(t(lang, "pause.btn.resume"), "pause:0")],
    ])


async def _set_pause(session: AsyncSession, user: User, days: int) -> str:
    repo = SqlScheduleRepository(session)
    if days == 0:
        await repo.set_pause(user.id, until=None)
        return t(user.language, "pause.resumed")
    now = datetime.now(tz=UTC)
    until = now + timedelta(days=days)
    await repo.set_pause(user.id, until=until)
    return t(user.language, "pause.set",
             until=fmt_when(until.isoformat(), user.language, user.timezone, now))


@router.message(Command("pause"))
async def cmd_pause(
    message: Message, command: CommandObject, user: User, session: AsyncSession
) -> None:
    lang = user.language
    args = (command.args or "").strip().lower()
    if not args:
        prefs = await SqlScheduleRepository(session).get(user.id)
        until = prefs.paused_until if prefs else None
        if until is not None and until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        now = datetime.now(tz=UTC)
        text = t(lang, "pause.ask")
        if until and until > now:
            text = t(lang, "pause.status",
                     until=fmt_when(until.isoformat(), lang, user.timezone, now)) + "\n\n" + text
        await message.answer(text, reply_markup=_pause_keyboard(lang))
        return
    if args in _RESUME_WORDS:
        await message.answer(await _set_pause(session, user, 0))
        return
    m = _PAUSE_RE.match(args)
    days = int(m.group(1)) if m else 0
    if not 1 <= days <= MAX_PAUSE_DAYS:
        await message.answer(t(lang, "pause.bad_args"))
        return
    await message.answer(await _set_pause(session, user, days))


@router.callback_query(F.data.startswith("pause:"))
async def on_pause(cb: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        days = int((cb.data or "").split(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    text = await _set_pause(session, user, max(0, min(days, MAX_PAUSE_DAYS)))
    if isinstance(cb.message, Message):
        await cb.message.edit_text(text)
    await cb.answer()


# --- /tidy -------------------------------------------------------------------

@router.message(Command("tidy"))
async def cmd_tidy(
    message: Message, command: CommandObject, user: User, session: AsyncSession
) -> None:
    lang = user.language
    repo = SqlScheduleRepository(session)
    arg = (command.args or "").strip().lower()
    if arg in ("on", "вкл"):
        await repo.set_tidy(user.id, enabled=True)
        await message.answer(t(lang, "tidy.on"))
    elif arg in ("off", "выкл"):
        await repo.set_tidy(user.id, enabled=False)
        await message.answer(t(lang, "tidy.off"))
    else:
        on = await repo.tidy_enabled(user.id)
        await message.answer(t(lang, "tidy.status_on" if on else "tidy.status_off"))
