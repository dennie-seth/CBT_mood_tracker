from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import t
from app.bot.keyboards import (
    migraine_after_start,
    migraine_over_button,
    migraine_single,
    migraine_symptoms,
    migraine_time_picker,
    migraine_yes_no,
    scale_1_to_10,
)
from app.bot.states import MigraineFlow
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.migraine_service import SYMPTOMS, MigraineService
from app.services.time import now_in_tz, parse_clock_time, today_in_tz

router = Router()

# Free-text steps shouldn't swallow other commands typed mid-flow.
_NOT_A_COMMAND = ~F.text.startswith("/")


def _svc(session: AsyncSession, cipher: FernetCipher) -> MigraineService:
    return MigraineService(entry_service(session, cipher))


async def _reply(
    event: Message | CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the button message for callbacks; answer typed messages."""
    if isinstance(event, CallbackQuery):
        if isinstance(event.message, Message):
            await event.message.edit_text(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


def _fmt_local(iso: str, tz_name: str) -> str:
    """'14:30' if it's today in the user's tz, else '2026-10-07 14:30'."""
    local = datetime.fromisoformat(iso).astimezone(pytz.timezone(tz_name))
    if local.date() == today_in_tz(tz_name):
        return local.strftime("%H:%M")
    return local.strftime("%Y-%m-%d %H:%M")


def _fmt_duration(minutes: int, lang: str) -> str:
    return t(lang, "migraine.duration", h=minutes // 60, m=minutes % 60)


def _minutes_ago(cb_data: str) -> datetime:
    minutes = int(cb_data.split(":", 1)[1])
    return datetime.now(tz=pytz.utc) - timedelta(minutes=minutes)


def _typed_time(text: str, tz_name: str) -> datetime:
    return parse_clock_time(text, now_in_tz(tz_name)).astimezone(pytz.utc)


# --- /migraine -------------------------------------------------------------

@router.message(Command("migraine"))
async def cmd_migraine(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    await state.clear()
    ongoing = await _svc(session, cipher).list_ongoing(
        user.id, on_or_before=today_in_tz(user.timezone)
    )
    if ongoing:
        latest = ongoing[-1]
        start = _fmt_local((latest.extra or {})["started_at"], user.timezone)
        await message.answer(
            t(user.language, "migraine.ongoing", start=start),
            reply_markup=migraine_over_button(user.language, latest.id, offer_new=True),
        )
        return
    await _ask_start(message, state, user)


@router.callback_query(F.data == "mg_new")
async def new_attack(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    await _ask_start(cb, state, user)


async def _ask_start(event: Message | CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(MigraineFlow.start_time)
    await state.set_data({})
    await _reply(
        event,
        t(user.language, "migraine.ask_start"),
        migraine_time_picker(user.language, "mg_st"),
    )


# --- start: time → intensity → aura → symptoms → medication → trigger ----

@router.callback_query(MigraineFlow.start_time, F.data.startswith("mg_st:"))
async def start_time_tapped(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    if cb.data is None:
        return
    await _got_start_time(cb, state, user, _minutes_ago(cb.data))


@router.message(MigraineFlow.start_time, _NOT_A_COMMAND)
async def start_time_typed(message: Message, state: FSMContext, user: User) -> None:
    try:
        started_at = _typed_time(message.text or "", user.timezone)
    except ValueError:
        await message.answer(t(user.language, "migraine.bad_time"))
        return
    await _got_start_time(message, state, user, started_at)


async def _got_start_time(
    event: Message | CallbackQuery, state: FSMContext, user: User, started_at: datetime
) -> None:
    await state.update_data(started_at=started_at.isoformat())
    await state.set_state(MigraineFlow.intensity)
    await _reply(event, t(user.language, "migraine.ask_intensity"), scale_1_to_10("mg_int"))


@router.callback_query(MigraineFlow.intensity, F.data.startswith("mg_int:"))
async def intensity_tapped(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    if cb.data is None:
        return
    await state.update_data(intensity=int(cb.data.split(":", 1)[1]))
    await state.set_state(MigraineFlow.aura)
    await _reply(cb, t(user.language, "migraine.ask_aura"), migraine_yes_no(user.language, "mg_aura"))


@router.callback_query(MigraineFlow.aura, F.data.startswith("mg_aura:"))
async def aura_tapped(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    if cb.data is None:
        return
    await state.update_data(aura=cb.data.endswith(":1"), symptoms=[])
    await state.set_state(MigraineFlow.symptoms)
    await _reply(cb, t(user.language, "migraine.ask_symptoms"), migraine_symptoms(user.language, []))


@router.callback_query(MigraineFlow.symptoms, F.data.startswith("mg_sym:"))
async def symptom_tapped(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    if cb.data is None or not isinstance(cb.message, Message):
        return
    key = cb.data.split(":", 1)[1]
    if key == "done":
        await state.set_state(MigraineFlow.medication)
        await _reply(
            cb,
            t(user.language, "migraine.ask_med"),
            migraine_single(user.language, "migraine.btn_nothing", "mg_med:none"),
        )
        return
    if key not in SYMPTOMS:
        await cb.answer()
        return
    selected: list[str] = (await state.get_data()).get("symptoms", [])
    selected = [s for s in selected if s != key] if key in selected else [*selected, key]
    await state.update_data(symptoms=selected)
    await cb.message.edit_reply_markup(reply_markup=migraine_symptoms(user.language, selected))
    await cb.answer()


@router.callback_query(MigraineFlow.medication, F.data == "mg_med:none")
async def medication_none(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    await _ask_trigger(cb, state, user)


@router.message(MigraineFlow.medication, _NOT_A_COMMAND)
async def medication_typed(message: Message, state: FSMContext, user: User) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    await state.update_data(medication_text=message.text.strip())
    await _ask_trigger(message, state, user)


async def _ask_trigger(event: Message | CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(MigraineFlow.trigger)
    await _reply(
        event,
        t(user.language, "migraine.ask_trigger"),
        migraine_single(user.language, "migraine.btn_skip", "mg_trg:none"),
    )


@router.callback_query(MigraineFlow.trigger, F.data == "mg_trg:none")
async def trigger_skipped(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    await _save_start(cb, state, user, session, cipher, trigger_text=None)


@router.message(MigraineFlow.trigger, _NOT_A_COMMAND)
async def trigger_typed(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    await _save_start(message, state, user, session, cipher, trigger_text=message.text)


async def _save_start(
    event: Message | CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
    *,
    trigger_text: str | None,
) -> None:
    data = await state.get_data()
    try:
        dto = await _svc(session, cipher).start(
            user,
            started_at=datetime.fromisoformat(data["started_at"]),
            intensity=int(data["intensity"]),
            aura=bool(data["aura"]),
            symptoms=list(data.get("symptoms", [])),
            medication_text=data.get("medication_text"),
            trigger_text=trigger_text,
        )
    except (KeyError, ValueError) as e:
        await state.clear()
        await _reply(event, t(user.language, "migraine.failed", err=e))
        return
    await state.clear()
    await _reply(
        event,
        t(
            user.language, "migraine.saved_ongoing",
            start=_fmt_local(data["started_at"], user.timezone),
            intensity=data["intensity"],
        ),
        migraine_after_start(user.language, dto.id),
    )


@router.callback_query(F.data.startswith("mg_still:"))
async def still_going(cb: CallbackQuery, user: User) -> None:
    if cb.data is None:
        return
    entry_id = int(cb.data.split(":", 1)[1])
    await _reply(
        cb,
        t(user.language, "migraine.still_going"),
        migraine_over_button(user.language, entry_id),
    )


# --- end: time → peak → (medication) → (relief) ---------------------------

@router.callback_query(F.data.startswith("mg_end:"))
async def over_tapped(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    if cb.data is None:
        return
    entry_id = int(cb.data.split(":", 1)[1])
    try:
        await _svc(session, cipher).get_ongoing(entry_id, user)
    except (LookupError, ValueError) as e:
        await state.clear()
        await _reply(cb, t(user.language, "migraine.failed", err=e))
        return
    await state.set_state(MigraineFlow.end_time)
    await state.set_data({"entry_id": entry_id})
    await _reply(cb, t(user.language, "migraine.ask_end"), migraine_time_picker(user.language, "mg_et"))


@router.callback_query(MigraineFlow.end_time, F.data.startswith("mg_et:"))
async def end_time_tapped(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    if cb.data is None:
        return
    await _got_end_time(cb, state, user, session, cipher, _minutes_ago(cb.data))


@router.message(MigraineFlow.end_time, _NOT_A_COMMAND)
async def end_time_typed(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    try:
        ended_at = _typed_time(message.text or "", user.timezone)
    except ValueError:
        await message.answer(t(user.language, "migraine.bad_time"))
        return
    await _got_end_time(message, state, user, session, cipher, ended_at)


async def _got_end_time(
    event: Message | CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
    ended_at: datetime,
) -> None:
    entry_id = int((await state.get_data())["entry_id"])
    try:
        attack = await _svc(session, cipher).get_ongoing(entry_id, user)
    except (LookupError, ValueError) as e:
        await state.clear()
        await _reply(event, t(user.language, "migraine.failed", err=e))
        return
    started_iso = (attack.extra or {})["started_at"]
    if ended_at < datetime.fromisoformat(started_iso):
        # Stay in end_time so the user can try again.
        await _reply(
            event,
            t(user.language, "migraine.end_before_start",
              start=_fmt_local(started_iso, user.timezone)),
            migraine_time_picker(user.language, "mg_et"),
        )
        return
    await state.update_data(
        ended_at=ended_at.isoformat(),
        has_medication=bool((attack.extra or {}).get("medication_text")),
    )
    await state.set_state(MigraineFlow.peak)
    await _reply(event, t(user.language, "migraine.ask_peak"), scale_1_to_10("mg_peak"))


@router.callback_query(MigraineFlow.peak, F.data.startswith("mg_peak:"))
async def peak_tapped(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    if cb.data is None:
        return
    await state.update_data(peak=int(cb.data.split(":", 1)[1]))
    if (await state.get_data()).get("has_medication"):
        await _ask_relief(cb, state, user)
        return
    await state.set_state(MigraineFlow.end_medication)
    await _reply(
        cb,
        t(user.language, "migraine.ask_end_med"),
        migraine_single(user.language, "migraine.btn_nothing", "mg_emed:none"),
    )


@router.callback_query(MigraineFlow.end_medication, F.data == "mg_emed:none")
async def end_medication_none(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    await _save_end(cb, state, user, session, cipher, relief=None)


@router.message(MigraineFlow.end_medication, _NOT_A_COMMAND)
async def end_medication_typed(message: Message, state: FSMContext, user: User) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    await state.update_data(medication_text=message.text.strip())
    await _ask_relief(message, state, user)


async def _ask_relief(event: Message | CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(MigraineFlow.relief)
    await _reply(event, t(user.language, "migraine.ask_relief"), scale_1_to_10("mg_rel"))


@router.callback_query(MigraineFlow.relief, F.data.startswith("mg_rel:"))
async def relief_tapped(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    if cb.data is None:
        return
    await _save_end(cb, state, user, session, cipher, relief=int(cb.data.split(":", 1)[1]))


async def _save_end(
    event: Message | CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
    *,
    relief: int | None,
) -> None:
    data = await state.get_data()
    try:
        dto = await _svc(session, cipher).end(
            int(data["entry_id"]),
            user,
            ended_at=datetime.fromisoformat(data["ended_at"]),
            peak_intensity=int(data["peak"]),
            relief=relief,
            medication_text=data.get("medication_text"),
        )
    except (KeyError, LookupError, ValueError) as e:
        await state.clear()
        await _reply(event, t(user.language, "migraine.failed", err=e))
        return
    await state.clear()
    await _reply(
        event,
        t(
            user.language, "migraine.saved_ended",
            duration=_fmt_duration(int((dto.extra or {})["duration_minutes"]), user.language),
            peak=int(dto.value_numeric or 0),
        ),
    )
