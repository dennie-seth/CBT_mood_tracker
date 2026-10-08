"""/day — rate the day in a few taps, one message edited in place.

Each answer is saved immediately (so stopping half-way keeps what was
given); the last step shows a summary with Undo / Add a note. Buttons carry
the metric they answer (`dc:<metric>:<value|skip>`), so a tap that doesn't
match the current step is ignored rather than mis-filed.
"""
from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.handlers.plain import format_readings
from app.bot.i18n import t
from app.bot.keyboards import entry_actions
from app.bot.states import DayFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()
log = structlog.get_logger(__name__)

DAY_METRICS: tuple[MetricType, ...] = (
    MetricType.MOOD, MetricType.ENERGY, MetricType.ANXIETY, MetricType.SLEEP_QUALITY,
)


def _question(step: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    metric = DAY_METRICS[step]
    rows = [
        [InlineKeyboardButton(text=str(n), callback_data=f"dc:{metric.value}:{n}") for n in rng]
        for rng in (range(1, 6), range(6, 11))
    ]
    rows.append([InlineKeyboardButton(
        text=t(lang, "day.btn.skip"), callback_data=f"dc:{metric.value}:skip"
    )])
    text = f"{step + 1}/{len(DAY_METRICS)} · {t(lang, f'day.q.{metric.value}')}"
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("day"))
async def cmd_day(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await state.set_state(DayFlow.active)
    await state.set_data({"step": 0, "ids": [], "readings": []})
    text, kb = _question(0, user.language)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("dc:"))
async def on_day(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    lang = user.language
    _, metric_raw, value_raw = ((cb.data or "") + "::").split(":")[:3]
    data = await state.get_data()
    step = data.get("step")
    if (
        await state.get_state() != DayFlow.active.state
        or not isinstance(step, int)
        or step >= len(DAY_METRICS)
        or DAY_METRICS[step].value != metric_raw
    ):
        await cb.answer(t(lang, "stale.button"))
        return

    ids: list[int] = list(data.get("ids", []))
    readings: list[list[float | str]] = list(data.get("readings", []))
    if value_raw != "skip":
        value = float(int(value_raw))
        dto = await entry_service(session, cipher).create(
            user, DAY_METRICS[step], value_numeric=value
        )
        ids.append(dto.id)
        readings.append([DAY_METRICS[step].value, value])

    step += 1
    msg = cb.message if isinstance(cb.message, Message) else None
    if step < len(DAY_METRICS):
        await state.update_data(step=step, ids=ids, readings=readings)
        if msg:
            text, kb = _question(step, lang)
            await msg.edit_text(text, reply_markup=kb)
        await cb.answer()
        return

    await state.clear()
    log.info("day_card_done", count=len(ids))
    pairs = [(MetricType(str(m)), float(v)) for m, v in readings]
    if msg:
        if pairs:
            await msg.edit_text(
                t(lang, "day.done", items=format_readings(pairs, lang)),
                reply_markup=entry_actions(lang, ids, pairs),
            )
        else:
            await msg.edit_text(t(lang, "day.done_empty"))
    await cb.answer()
