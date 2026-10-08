"""Text sent outside any command.

1. "mood 6 anxiety 7 slept 6.5" → logged at once (parsed locally, no AI),
   with Undo / Add a note buttons.
2. Anything else → "What should I do with this?" [note] [thought record]
   [ask Claude] [nothing]. The text waits in FSM data (encrypted at rest by
   PgFsmStorage), never in callback data, and nothing goes to Claude unless
   the user taps "Ask Claude".

Registered last so every command and flow gets the message first.
"""
from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.handlers.ask import run_ask
from app.bot.i18n import t
from app.bot.keyboards import entry_actions
from app.bot.states import PlainTextFlow, ThoughtFlow
from app.di import Container
from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.quick_log import parse_quick_log

router = Router()
log = structlog.get_logger(__name__)


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def format_readings(readings: list[tuple[MetricType, float]], lang: str) -> str:
    return ", ".join(f"{t(lang, f'short.{m.value}')} {_fmt(v)}" for m, v in readings)


@router.message(
    StateFilter(None, PlainTextFlow.pending), F.text, ~F.text.startswith("/")
)
async def plain_text(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    text = (message.text or "").strip()
    lang = user.language

    readings = parse_quick_log(text)
    if readings:
        await state.clear()
        svc = entry_service(session, cipher)
        dtos = [await svc.create(user, m, value_numeric=v) for m, v in readings]
        log.info("quick_log", count=len(dtos))
        await message.answer(
            t(lang, "quick.saved", items=format_readings(readings, lang),
              date=dtos[0].entry_date.isoformat()),
            reply_markup=entry_actions(lang, [d.id for d in dtos], readings),
        )
        return

    await state.set_state(PlainTextFlow.pending)
    await state.set_data({"pending_text": text})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "plain.btn.note"), callback_data="pt:note"),
            InlineKeyboardButton(text=t(lang, "plain.btn.thought"), callback_data="pt:thought"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "plain.btn.ask"), callback_data="pt:ask"),
            InlineKeyboardButton(text=t(lang, "plain.btn.nothing"), callback_data="pt:no"),
        ],
    ])
    await message.answer(t(lang, "plain.offer"), reply_markup=kb)


@router.callback_query(F.data.startswith("pt:"))
async def on_plain_choice(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, container: Container,
) -> None:
    lang = user.language
    choice = (cb.data or "").split(":", 1)[1]
    pending = (
        (await state.get_data()).get("pending_text")
        if await state.get_state() == PlainTextFlow.pending.state
        else None
    )
    if not pending:
        await cb.answer(t(lang, "plain.expired"), show_alert=True)
        return
    msg = cb.message if isinstance(cb.message, Message) else None
    await state.clear()

    if choice == "note":
        dto = await entry_service(session, container.cipher).create(
            user, MetricType.NOTE, value_text=pending
        )
        if msg:
            await msg.edit_text(
                t(lang, "note.saved", date=dto.entry_date.isoformat()),
                reply_markup=entry_actions(lang, [dto.id]),
            )
    elif choice == "thought":
        await state.set_state(ThoughtFlow.automatic_thought)
        await state.update_data(situation_text=pending)
        if msg:
            await msg.edit_text(t(lang, "thought.ask_auto"))
    elif choice == "ask":
        if msg:
            await msg.edit_text(t(lang, "ask.thinking"))
            await run_ask(msg, question=pending, user=user, session=session, container=container)
    elif msg:
        await msg.edit_text(t(lang, "plain.dismissed"))
    await cb.answer()
