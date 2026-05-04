from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.keyboards import metric_picker, scale_1_to_10
from app.bot.states import LogFlow
from app.domain.enums import METRIC_LABELS, NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()


@router.message(Command("log"))
async def cmd_log(message: Message, state: FSMContext) -> None:
    await state.set_state(LogFlow.pick_metric)
    await message.answer("What do you want to log?", reply_markup=metric_picker("log"))


@router.callback_query(LogFlow.pick_metric, F.data.startswith("log:"))
async def picked_metric(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.data is None or cb.message is None:
        return
    name = cb.data.split(":", 1)[1]
    metric = MetricType(name)
    await state.update_data(metric=metric.value)
    await state.set_state(LogFlow.enter_value)
    if metric in NUMERIC_METRICS and metric is not MetricType.SLEEP_HOURS:
        await cb.message.edit_text(
            f"{METRIC_LABELS[metric]} — pick 1-10:",
            reply_markup=scale_1_to_10("logval"),
        )
    elif metric is MetricType.SLEEP_HOURS:
        await cb.message.edit_text(
            f"{METRIC_LABELS[metric]} — type hours (e.g. 7.5):"
        )
    else:
        await cb.message.edit_text(
            f"{METRIC_LABELS[metric]} — type your entry:"
        )
    await cb.answer()


@router.callback_query(LogFlow.enter_value, F.data.startswith("logval:"))
async def numeric_chosen(
    cb: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if cb.data is None or cb.message is None:
        return
    value = int(cb.data.split(":", 1)[1])
    data = await state.get_data()
    metric = MetricType(data["metric"])
    svc = entry_service(session, cipher)
    dto = await svc.create(user, metric, value_numeric=float(value))
    await state.clear()
    await cb.message.edit_text(
        f"Logged {METRIC_LABELS[metric]} = {value} for {dto.entry_date.isoformat()}."
    )
    await cb.answer()


@router.message(LogFlow.enter_value)
async def value_typed(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if message.text is None:
        return
    data = await state.get_data()
    metric = MetricType(data["metric"])
    svc = entry_service(session, cipher)

    if metric in NUMERIC_METRICS:
        try:
            value = float(message.text.replace(",", "."))
        except ValueError:
            await message.answer("Please send a number.")
            return
        dto = await svc.create(user, metric, value_numeric=value)
    else:
        dto = await svc.create(user, metric, value_text=message.text.strip())

    await state.clear()
    await message.answer(
        f"Logged {METRIC_LABELS[metric]} for {dto.entry_date.isoformat()}."
    )
