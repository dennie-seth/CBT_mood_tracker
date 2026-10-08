"""/breathe — box breathing or 5-4-3-2-1 grounding, no typing needed.

Box breathing edits ONE message once per 4-second phase (well within
Telegram's edit limits) and runs as a background task so the handler
returns immediately; "Stop" flags it via an in-memory set. Grounding is a
tap-through: one edited message, one step per tap.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.i18n import metric_label, t
from app.bot.keyboards import scale_1_to_10
from app.bot.states import QuickFlow
from app.bot.support import exercises_keyboard
from app.domain.enums import MetricType
from app.domain.models import User

router = Router()
log = structlog.get_logger(__name__)

ROUNDS = 4
PHASE_SECONDS = 4
_PHASES: tuple[tuple[str, str], ...] = (
    ("breathe.in", "⬆️"), ("breathe.hold_in", "⏸"), ("breathe.out", "⬇️"), ("breathe.hold_out", "⏸"),
)
_GROUND_STEPS = (5, 4, 3, 2, 1)
_stop_requests: set[tuple[int, int]] = set()
_tasks: set[asyncio.Task[None]] = set()

Sleep = Callable[[float], Awaitable[object]]


def request_stop(chat_id: int, message_id: int) -> None:
    _stop_requests.add((chat_id, message_id))


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


async def _edit(msg: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramAPIError as exc:  # message deleted (/hide) or unchanged
        log.info("breathe_edit_failed", error_type=type(exc).__name__)


async def run_box_breathing(
    msg: Message, lang: str, *, rounds: int = ROUNDS, sleep: Sleep = asyncio.sleep
) -> None:
    key = (msg.chat.id, msg.message_id)
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[_btn(t(lang, "breathe.btn.stop"), "br:stop")]])
    try:
        for r in range(1, rounds + 1):
            for phase_key, icon in _PHASES:
                if key in _stop_requests:
                    await _edit(msg, t(lang, "breathe.stopped"))
                    return
                title = t(lang, "breathe.title", round=r, total=rounds)
                await _edit(msg, f"{title}\n\n{icon} {t(lang, phase_key)}", stop_kb)
                await sleep(PHASE_SECONDS)
        if key in _stop_requests:
            await _edit(msg, t(lang, "breathe.stopped"))
            return
        await _edit(msg, t(lang, "breathe.done"), InlineKeyboardMarkup(inline_keyboard=[
            [_btn(t(lang, "breathe.btn.log_anxiety"), "br:log")],
        ]))
    finally:
        _stop_requests.discard(key)


def _ground_step(n: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    nxt = n - 1
    return t(lang, f"ground.{n}"), InlineKeyboardMarkup(inline_keyboard=[
        [_btn(t(lang, "ground.btn.next"), f"gr:{nxt}")],
    ])


@router.message(Command("breathe"))
async def cmd_breathe(message: Message, user: User) -> None:
    await message.answer(t(user.language, "breathe.choose"), reply_markup=exercises_keyboard(user.language))


@router.callback_query(F.data.startswith("br:") | F.data.startswith("gr:"))
async def on_breathe(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    lang = user.language
    msg = cb.message if isinstance(cb.message, Message) else None
    data = cb.data or ""
    if msg is None:
        await cb.answer()
        return

    if data == "br:box":
        task = asyncio.ensure_future(run_box_breathing(msg, lang))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    elif data == "br:stop":
        request_stop(msg.chat.id, msg.message_id)
    elif data == "br:ground":
        await _edit(msg, *_ground_step(_GROUND_STEPS[0], lang))
    elif data.startswith("gr:"):
        try:
            n = int(data.split(":", 1)[1])
        except ValueError:
            n = 0
        if n in _GROUND_STEPS:
            await _edit(msg, *_ground_step(n, lang))
        else:
            await _edit(msg, t(lang, "ground.done"))
    elif data == "br:log":
        await state.clear()
        await state.set_state(QuickFlow.pick_value)
        await state.update_data(metric=MetricType.ANXIETY.value)
        await msg.answer(
            t(lang, "log.enter_numeric", label=metric_label(MetricType.ANXIETY, lang)),
            reply_markup=scale_1_to_10(callback_prefix="quick"),
        )
    await cb.answer()
