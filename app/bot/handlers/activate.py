from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.keyboards import plan_picker, plan_when_picker, scale_1_to_10
from app.bot.states import ActivateFlow, DoneFlow, SkipFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.services.activation_service import ActivationService
from app.services.entry_service import EntryService
from app.services.time import today_in_tz

router = Router()


def _activation_service(session: AsyncSession, cipher: FernetCipher) -> ActivationService:
    es = EntryService(SqlEntryRepository(session), cipher)
    return ActivationService(es)


# --- /activate ----------------------------------------------------------

@router.message(Command("activate"))
async def cmd_activate(message: Message, state: FSMContext) -> None:
    await state.set_state(ActivateFlow.plan_text)
    await message.answer(
        "What would lift your mood, even slightly? Send one short line."
    )


@router.message(ActivateFlow.plan_text)
async def activate_plan_text(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer("Please send a short text.")
        return
    await state.update_data(plan_text=message.text.strip())
    await state.set_state(ActivateFlow.pick_when)
    await message.answer("When?", reply_markup=plan_when_picker())


@router.callback_query(ActivateFlow.pick_when, F.data.startswith("plan_when:"))
async def activate_pick_when(
    cb: CallbackQuery,
    state: FSMContext,
    user: User,
) -> None:
    if cb.data is None or cb.message is None:
        return
    offset = int(cb.data.split(":", 1)[1])
    target = today_in_tz(user.timezone) + timedelta(days=offset)
    await state.update_data(planned_for=target.isoformat())
    await state.set_state(ActivateFlow.pick_predicted_effect)
    await cb.message.edit_text(
        f"Planned for {target.isoformat()}. "
        "How much do you predict it will lift your mood? (1-10)",
        reply_markup=scale_1_to_10("plan_pred"),
    )
    await cb.answer()


@router.callback_query(ActivateFlow.pick_predicted_effect, F.data.startswith("plan_pred:"))
async def activate_pick_predicted_effect(
    cb: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if cb.data is None or cb.message is None:
        return
    predicted = int(cb.data.split(":", 1)[1])
    data = await state.get_data()
    plan_text: str = data["plan_text"]
    planned_for = date.fromisoformat(data["planned_for"])

    es = EntryService(SqlEntryRepository(session), cipher)
    # `recorded_at` is noon-on-planned-for-in-user's-tz (the same convention
    # /backfill uses) so day-bucketing and timezone DST behave well.
    from datetime import datetime, time
    import pytz
    tz = pytz.timezone(user.timezone)
    recorded_at = tz.localize(datetime.combine(planned_for, time(12, 0))).astimezone(pytz.utc)

    extra: dict[str, Any] = {
        "plan_text": plan_text,
        "planned_for": planned_for.isoformat(),
        "predicted_effect": predicted,
        "status": "scheduled",
    }
    await es.create(
        user, MetricType.ACTIVITY_PLAN, extra=extra, recorded_at=recorded_at
    )
    await state.clear()
    await cb.message.edit_text(
        f"Plan saved for {planned_for.isoformat()} (predicted +{predicted}). "
        "Use /done when finished, or /skip if not."
    )
    await cb.answer()


# --- /plans -------------------------------------------------------------

@router.message(Command("plans"))
async def cmd_plans(
    message: Message,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    svc = _activation_service(session, cipher)
    plans = await svc.list_open_plans(
        user.id, on_or_before=today_in_tz(user.timezone) + timedelta(days=30)
    )
    if not plans:
        await message.answer(
            "No open plans. /activate to add one."
        )
        return
    lines = ["Open plans:"]
    for p in plans:
        text = (p.extra or {}).get("plan_text", "(no description)")
        pred = (p.extra or {}).get("predicted_effect")
        weekday = p.entry_date.strftime("%a")
        suffix = f" (predicted +{pred})" if pred is not None else ""
        lines.append(f"• {weekday} {p.entry_date.isoformat()} — {text}{suffix}")
    await message.answer("\n".join(lines))


# --- /done --------------------------------------------------------------

@router.message(Command("done"))
async def cmd_done(
    message: Message,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    svc = _activation_service(session, cipher)
    plans = await svc.list_open_plans(
        user.id, on_or_before=today_in_tz(user.timezone) + timedelta(days=30)
    )
    if not plans:
        await message.answer("No open plans. /activate to add one.")
        return
    await message.answer("Which one did you complete?", reply_markup=plan_picker(plans, "bf_done"))


@router.callback_query(F.data.startswith("bf_done:"))
async def done_pick_plan(
    cb: CallbackQuery,
    state: FSMContext,
) -> None:
    if cb.data is None or cb.message is None:
        return
    entry_id = int(cb.data.split(":", 1)[1])
    await state.set_state(DoneFlow.pick_actual_effect)
    await state.update_data(entry_id=entry_id)
    await cb.message.edit_text(
        "How much did it actually lift your mood? (1-10)",
        reply_markup=scale_1_to_10("done_act"),
    )
    await cb.answer()


@router.callback_query(DoneFlow.pick_actual_effect, F.data.startswith("done_act:"))
async def done_pick_actual_effect(
    cb: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if cb.data is None or cb.message is None:
        return
    actual = int(cb.data.split(":", 1)[1])
    data = await state.get_data()
    entry_id = int(data["entry_id"])
    svc = _activation_service(session, cipher)
    try:
        updated = await svc.mark_done(entry_id, user, actual_effect=actual)
    except (LookupError, ValueError, PermissionError) as e:
        await cb.message.edit_text(f"Couldn't mark done: {e}")
        await state.clear()
        await cb.answer()
        return
    pred = (updated.extra or {}).get("predicted_effect")
    if pred is not None:
        body = f"Done — predicted +{pred}, actual +{actual}. Nice."
    else:
        body = f"Done — actual +{actual}. Nice."
    await state.clear()
    await cb.message.edit_text(body)
    await cb.answer()


# --- /skip --------------------------------------------------------------

@router.message(Command("skip"))
async def cmd_skip(
    message: Message,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    svc = _activation_service(session, cipher)
    plans = await svc.list_open_plans(
        user.id, on_or_before=today_in_tz(user.timezone) + timedelta(days=30)
    )
    if not plans:
        await message.answer("No open plans to skip.")
        return
    await message.answer("Which one are you skipping?", reply_markup=plan_picker(plans, "bf_skip"))


@router.callback_query(F.data.startswith("bf_skip:"))
async def skip_pick_plan(
    cb: CallbackQuery,
    state: FSMContext,
) -> None:
    if cb.data is None or cb.message is None:
        return
    entry_id = int(cb.data.split(":", 1)[1])
    await state.set_state(SkipFlow.enter_reason)
    await state.update_data(entry_id=entry_id)
    await cb.message.edit_text(
        "One-line reason? (or send /cancel to skip without one)"
    )
    await cb.answer()


@router.message(SkipFlow.enter_reason)
async def skip_enter_reason(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    reason = (message.text or "").strip() or None
    data = await state.get_data()
    entry_id = int(data["entry_id"])
    svc = _activation_service(session, cipher)
    try:
        await svc.mark_skipped(entry_id, user, reason_text=reason)
    except (LookupError, ValueError, PermissionError) as e:
        await message.answer(f"Couldn't skip: {e}")
        await state.clear()
        return
    await state.clear()
    await message.answer(
        "Skipped. No judgement — sometimes the planning itself is the work."
    )
