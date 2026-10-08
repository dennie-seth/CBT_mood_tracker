"""/migraine — the attack card.

One tap saves an attack (intensity, start = now). Everything else is an
optional button on the card, editable while the attack is open and after it
ended. Buttons carry `mg:<action>:<entry_id>[:<arg>]` and work without FSM
state; only the three free-text steps (a typed time, medication, own trigger)
use state, and any card tap cancels a pending text step.
"""
from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import migraine_card as card
from app.bot.deps import entry_service
from app.bot.i18n import t
from app.bot.states import MigraineFlow
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import EntryDTO
from app.services.migraine_service import (
    SYMPTOMS,
    TRIGGERS,
    MigraineError,
    MigraineErrorCode,
    MigraineService,
)
from app.services.time import now_in_tz, parse_moment, today_in_tz

router = Router()
log = structlog.get_logger(__name__)

# Free-text steps shouldn't swallow other commands typed mid-flow.
_NOT_A_COMMAND = ~F.text.startswith("/")


def _svc(session: AsyncSession, cipher: FernetCipher) -> MigraineService:
    return MigraineService(entry_service(session, cipher))


def _error_text(lang: str, exc: Exception) -> str:
    """Friendly, translated text for a failed step. Logs only the error code
    (never entry payloads)."""
    if isinstance(exc, MigraineError):
        log.info("migraine.step_failed", code=exc.code.value)
        return t(lang, f"migraine.err.{exc.code.value}")
    log.warning("migraine.step_failed", error_type=type(exc).__name__)
    return t(lang, "migraine.err.generic")


def _render(
    attack: EntryDTO, user: User, footer: str | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    return card.render_card(
        attack, user.language, user.timezone, datetime.now(tz=UTC), footer=footer
    )


def _closed_footer(user: User) -> str:
    return t(user.language, "migraine.card.closed_footer")


async def _retire_prompt(bot: Bot, message: Message, data: dict[str, Any], lang: str) -> None:
    """Strip the buttons off the prompt a typed answer replied to, so old
    buttons can't be tapped out of context."""
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        return
    # Already edited / too old — nothing to tidy.
    with contextlib.suppress(TelegramBadRequest):
        await bot.edit_message_text(
            text=t(lang, "migraine.saved_note"),
            chat_id=message.chat.id,
            message_id=prompt_id,
        )


# --- /migraine ---------------------------------------------------------------

@router.message(Command("migraine"))
async def cmd_migraine(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    await state.clear()
    open_attacks = await _svc(session, cipher).list_open(
        user.id, today=today_in_tz(user.timezone)
    )
    if not open_attacks:
        await message.answer(
            t(user.language, "migraine.ask_intensity"), reply_markup=card.scale("new", 0)
        )
        return
    for n, attack in enumerate(open_attacks):
        text, kb = _render(attack, user)
        if n == len(open_attacks) - 1:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                *kb.inline_keyboard,
                [InlineKeyboardButton(
                    text=t(user.language, "migraine.btn.new"),
                    callback_data=card.cb("newask", 0),
                )],
            ])
        await message.answer(text, reply_markup=kb)


# --- card buttons --------------------------------------------------------------

@dataclass
class _Tap:
    cb: CallbackQuery
    state: FSMContext
    user: User
    svc: MigraineService
    entry_id: int
    args: list[str]
    data: dict[str, Any] = field(default_factory=dict)  # FSM data before the tap

    @property
    def lang(self) -> str:
        return self.user.language

    def arg_int(self) -> int:
        return int(self.args[0])

    def minutes_ago(self) -> datetime:
        return datetime.now(tz=UTC) - timedelta(minutes=self.arg_int())

    async def show(self, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
        if isinstance(self.cb.message, Message):
            await self.cb.message.edit_text(text, reply_markup=kb)
        await self.cb.answer()

    async def show_card(self, attack: EntryDTO, footer: str | None = None) -> None:
        await self.show(*_render(attack, self.user, footer))

    async def ask_text(
        self, st: State, text: str, kb: InlineKeyboardMarkup | None, **data: Any
    ) -> None:
        prompt_id = self.cb.message.message_id if isinstance(self.cb.message, Message) else None
        await self.state.set_state(st)
        await self.state.set_data({"entry_id": self.entry_id, "prompt_id": prompt_id, **data})
        await self.show(text, kb)


_Action = Callable[[_Tap], Awaitable[None]]
_ACTIONS: dict[str, _Action] = {}


def _action(name: str) -> Callable[[_Action], _Action]:
    def register(fn: _Action) -> _Action:
        _ACTIONS[name] = fn
        return fn
    return register


@router.callback_query(F.data.startswith("mg:"))
async def on_card(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    parts = (cb.data or "").split(":")
    action = _ACTIONS.get(parts[1]) if len(parts) >= 3 else None
    if action is None or not parts[2].isdigit():
        await stale_button(cb, user)
        return
    data = await state.get_data()
    await state.clear()  # any tap cancels a pending text step
    tap = _Tap(cb, state, user, _svc(session, cipher), int(parts[2]), parts[3:], data)
    try:
        await action(tap)
    except MigraineError as e:
        await cb.answer(_error_text(user.language, e), show_alert=True)
    except (ValueError, IndexError):
        await stale_button(cb, user)


# Starting

@_action("newask")
async def _newask(tap: _Tap) -> None:
    await tap.show(t(tap.lang, "migraine.ask_intensity"), card.scale("new", 0))


@_action("new")
async def _new(tap: _Tap) -> None:
    attack = await tap.svc.start(tap.user, intensity=tap.arg_int())
    log.info("migraine.started", entry_id=attack.id)
    await tap.show_card(attack)


@_action("card")
async def _card(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.get(tap.entry_id, tap.user))


# Closing: end time → worst → medication? → relief

@_action("over")
async def _over(tap: _Tap) -> None:
    await tap.svc.get_ongoing(tap.entry_id, tap.user)
    forgot = [[InlineKeyboardButton(
        text=t(tap.lang, "migraine.btn.forgot_end"),
        callback_data=card.cb("forgot", tap.entry_id),
    )]]
    await tap.ask_text(
        MigraineFlow.typed_time,
        t(tap.lang, "migraine.ask_end"),
        card.time_picker(tap.lang, "end", tap.entry_id, include_now=True, extra_rows=forgot),
        field="end", closing=True,
    )


@_action("end")
async def _end(tap: _Tap) -> None:
    await tap.svc.end(tap.entry_id, tap.user, ended_at=tap.minutes_ago())
    log.info("migraine.ended", entry_id=tap.entry_id)
    await tap.show(t(tap.lang, "migraine.ask_peak_end"), card.scale("pkc", tap.entry_id))


@_action("forgot")
async def _forgot(tap: _Tap) -> None:
    await tap.svc.close_unknown_end(tap.entry_id, tap.user)
    await tap.show(t(tap.lang, "migraine.ask_peak_end"), card.scale("pkc", tap.entry_id))


@_action("pkc")
async def _peak_closing(tap: _Tap) -> None:
    attack = await tap.svc.update(tap.entry_id, tap.user, peak=tap.arg_int())
    if (attack.extra or {}).get("medication_text"):
        await tap.show(t(tap.lang, "migraine.ask_relief"), card.scale("rlc", tap.entry_id))
        return
    await _ask_medication(tap, closing=True)


@_action("rlc")
async def _relief_closing(tap: _Tap) -> None:
    attack = await tap.svc.update(tap.entry_id, tap.user, relief=tap.arg_int())
    await tap.show_card(attack, _closed_footer(tap.user))


@_action("nomed")
async def _no_med(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.get(tap.entry_id, tap.user), _closed_footer(tap.user))


# Times

@_action("start")
async def _start_time(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    await tap.ask_text(
        MigraineFlow.typed_time,
        t(tap.lang, "migraine.ask_start"),
        card.time_picker(tap.lang, "st", tap.entry_id, include_now=False),
        field="start",
    )


@_action("st")
async def _start_picked(tap: _Tap) -> None:
    await tap.show_card(
        await tap.svc.update(tap.entry_id, tap.user, started_at=tap.minutes_ago())
    )


@_action("endtime")
async def _end_time(tap: _Tap) -> None:
    attack = await tap.svc.get(tap.entry_id, tap.user)
    if (attack.extra or {}).get("status") != "ended":
        raise MigraineError(MigraineErrorCode.NOT_ENDED)
    await tap.ask_text(
        MigraineFlow.typed_time,
        t(tap.lang, "migraine.ask_end"),
        card.time_picker(tap.lang, "et", tap.entry_id, include_now=True),
        field="end", closing=False,
    )


@_action("et")
async def _end_picked(tap: _Tap) -> None:
    await tap.show_card(
        await tap.svc.update(tap.entry_id, tap.user, ended_at=tap.minutes_ago())
    )


# Intensity, aura, symptoms

@_action("worse")
async def _worse(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    await tap.show(t(tap.lang, "migraine.ask_peak"), card.scale("pk", tap.entry_id, tap.lang))


@_action("pk")
async def _peak(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.update(tap.entry_id, tap.user, peak=tap.arg_int()))


@_action("aura")
async def _aura(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    await tap.show(t(tap.lang, "migraine.ask_aura"), card.yes_no(tap.lang, tap.entry_id))


@_action("au")
async def _aura_set(tap: _Tap) -> None:
    await tap.show_card(
        await tap.svc.update(tap.entry_id, tap.user, aura=tap.args[0] == "1")
    )


def _toggle(selected: list[str], key: str) -> list[str]:
    return [s for s in selected if s != key] if key in selected else [*selected, key]


async def _show_symptoms(tap: _Tap, attack: EntryDTO) -> None:
    await tap.show(
        t(tap.lang, "migraine.ask_symptoms"),
        card.toggles(
            tap.lang, tap.entry_id, action="sy", label_prefix="sym",
            keys=SYMPTOMS, selected=(attack.extra or {}).get("symptoms") or [],
        ),
    )


@_action("sym")
async def _symptoms(tap: _Tap) -> None:
    await _show_symptoms(tap, await tap.svc.get(tap.entry_id, tap.user))


@_action("sy")
async def _symptom_toggle(tap: _Tap) -> None:
    attack = await tap.svc.get(tap.entry_id, tap.user)
    selected = _toggle((attack.extra or {}).get("symptoms") or [], tap.args[0])
    await _show_symptoms(tap, await tap.svc.update(tap.entry_id, tap.user, symptoms=selected))


# Triggers

async def _show_triggers(tap: _Tap, attack: EntryDTO) -> None:
    x = attack.extra or {}
    extra_rows = [[InlineKeyboardButton(
        text=t(tap.lang, "migraine.btn.own_trigger"),
        callback_data=card.cb("tgt", tap.entry_id),
    )]]
    if x.get("trigger_text"):
        extra_rows.append([InlineKeyboardButton(
            text=f"✖ “{x['trigger_text'][:30]}”",
            callback_data=card.cb("tgx", tap.entry_id),
        )])
    await tap.show(
        t(tap.lang, "migraine.ask_triggers"),
        card.toggles(
            tap.lang, tap.entry_id, action="tg", label_prefix="trg",
            keys=TRIGGERS, selected=x.get("triggers") or [], extra_rows=extra_rows,
        ),
    )


@_action("trg")
async def _triggers(tap: _Tap) -> None:
    await _show_triggers(tap, await tap.svc.get(tap.entry_id, tap.user))


@_action("tg")
async def _trigger_toggle(tap: _Tap) -> None:
    attack = await tap.svc.get(tap.entry_id, tap.user)
    selected = _toggle((attack.extra or {}).get("triggers") or [], tap.args[0])
    await _show_triggers(tap, await tap.svc.update(tap.entry_id, tap.user, triggers=selected))


@_action("tgt")
async def _trigger_text(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t(tap.lang, "migraine.btn.back"), callback_data=card.cb("trg", tap.entry_id),
    )]])
    await tap.ask_text(MigraineFlow.trigger_text, t(tap.lang, "migraine.ask_trigger_text"), back)


@_action("tgx")
async def _trigger_text_clear(tap: _Tap) -> None:
    await _show_triggers(tap, await tap.svc.update(tap.entry_id, tap.user, trigger_text=None))


# Medication & relief

async def _ask_medication(tap: _Tap, *, closing: bool) -> None:
    attack = await tap.svc.get(tap.entry_id, tap.user)
    meds = await tap.svc.recent_medications(tap.user.id, today=today_in_tz(tap.user.timezone))
    await tap.ask_text(
        MigraineFlow.medication,
        t(tap.lang, "migraine.ask_end_med" if closing else "migraine.ask_med"),
        card.med_picker(
            tap.lang, tap.entry_id, meds, closing=closing,
            has_med=bool((attack.extra or {}).get("medication_text")),
        ),
        meds=meds, closing=closing,
    )


@_action("med")
async def _med(tap: _Tap) -> None:
    await _ask_medication(tap, closing=False)


@_action("mp")
async def _med_picked(tap: _Tap) -> None:
    meds: list[str] = tap.data.get("meds") or []
    med = meds[tap.arg_int()]  # IndexError → stale button
    attack = await tap.svc.update(tap.entry_id, tap.user, medication_text=med)
    if tap.data.get("closing"):
        await tap.show(t(tap.lang, "migraine.ask_relief"), card.scale("rlc", tap.entry_id))
        return
    await tap.show_card(attack)


@_action("mx")
async def _med_clear(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.update(tap.entry_id, tap.user, medication_text=None))


@_action("relief")
async def _relief(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    await tap.show(t(tap.lang, "migraine.ask_relief"), card.scale("rl", tap.entry_id, tap.lang))


@_action("rl")
async def _relief_set(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.update(tap.entry_id, tap.user, relief=tap.arg_int()))


# Reminders

@_action("mute")
async def _mute(tap: _Tap) -> None:
    await tap.show_card(await tap.svc.mute_reminders(tap.entry_id, tap.user))


# Delete

@_action("del")
async def _delete(tap: _Tap) -> None:
    await tap.svc.get(tap.entry_id, tap.user)
    await tap.show(t(tap.lang, "migraine.ask_delete"), card.confirm_delete(tap.lang, tap.entry_id))


@_action("dely")
async def _delete_yes(tap: _Tap) -> None:
    await tap.svc.delete(tap.entry_id, tap.user)
    log.info("migraine.deleted", entry_id=tap.entry_id)
    await tap.show(t(tap.lang, "migraine.deleted"))


# --- typed answers -------------------------------------------------------------

@router.message(MigraineFlow.typed_time, _NOT_A_COMMAND)
async def typed_time(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher, bot: Bot,
) -> None:
    lang = user.language
    try:
        moment = parse_moment(message.text or "", now_in_tz(user.timezone)).astimezone(UTC)
    except ValueError:
        await message.answer(t(lang, "migraine.bad_time"))
        return
    data = await state.get_data()
    svc = _svc(session, cipher)
    entry_id = int(data["entry_id"])
    try:
        if data.get("field") == "start":
            reply = _render(await svc.update(entry_id, user, started_at=moment), user)
        elif data.get("closing"):
            await svc.end(entry_id, user, ended_at=moment)
            reply = (t(lang, "migraine.ask_peak_end"), card.scale("pkc", entry_id))
        else:
            reply = _render(await svc.update(entry_id, user, ended_at=moment), user)
    except MigraineError as e:
        await message.answer(_error_text(lang, e))  # stay in this step
        return
    await state.clear()
    await _retire_prompt(bot, message, data, lang)
    await message.answer(reply[0], reply_markup=reply[1])


@router.message(MigraineFlow.medication, _NOT_A_COMMAND)
async def typed_medication(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher, bot: Bot,
) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    data = await state.get_data()
    entry_id = int(data["entry_id"])
    try:
        attack = await _svc(session, cipher).update(
            entry_id, user, medication_text=message.text
        )
    except MigraineError as e:
        await state.clear()
        await message.answer(_error_text(user.language, e))
        return
    await state.clear()
    await _retire_prompt(bot, message, data, user.language)
    if data.get("closing"):
        await message.answer(
            t(user.language, "migraine.ask_relief"), reply_markup=card.scale("rlc", entry_id)
        )
        return
    text, kb = _render(attack, user)
    await message.answer(text, reply_markup=kb)


@router.message(MigraineFlow.trigger_text, _NOT_A_COMMAND)
async def typed_trigger(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher, bot: Bot,
) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    data = await state.get_data()
    try:
        attack = await _svc(session, cipher).update(
            int(data["entry_id"]), user, trigger_text=message.text
        )
    except MigraineError as e:
        await state.clear()
        await message.answer(_error_text(user.language, e))
        return
    await state.clear()
    await _retire_prompt(bot, message, data, user.language)
    text, kb = _render(attack, user)
    await message.answer(text, reply_markup=kb)


# --- leftovers -----------------------------------------------------------------

@router.callback_query(F.data.startswith("mg"))
async def stale_button(cb: CallbackQuery, user: User) -> None:
    """Buttons from an older step or the previous version of this flow:
    answer so Telegram's spinner stops, and point to the latest message."""
    await cb.answer(t(user.language, "migraine.stale_button"))
