from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.keyboards import scale_1_to_10
from app.bot.states import QuickFlow
from app.domain.enums import METRIC_LABELS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()

QUICK_COMMANDS: dict[str, MetricType] = {
    "mood": MetricType.MOOD,
    "sleep": MetricType.SLEEP_QUALITY,
    "energy": MetricType.ENERGY,
    "hunger": MetricType.HUNGER,
    "anxiety": MetricType.ANXIETY,
    "stress": MetricType.STRESS,
    "pain": MetricType.PAIN,
    "irritability": MetricType.IRRITABILITY,
    "focus": MetricType.FOCUS,
}


def _make_handler(cmd: str, metric: MetricType):
    async def handler(message: Message, state: FSMContext) -> None:
        await state.set_state(QuickFlow.pick_value)
        await state.update_data(metric=metric.value)
        await message.answer(
            f"{METRIC_LABELS[metric]} — pick 1-10:",
            reply_markup=scale_1_to_10(callback_prefix="quick"),
        )

    handler.__name__ = f"cmd_{cmd}"
    return handler


for _cmd, _metric in QUICK_COMMANDS.items():
    router.message.register(_make_handler(_cmd, _metric), Command(_cmd))


# Sleep duration is special: requires a float, not a 1-10 scale.
@router.message(Command("sleephours"))
async def cmd_sleephours(message: Message, state: FSMContext) -> None:
    await state.set_state(QuickFlow.pick_value)
    await state.update_data(metric=MetricType.SLEEP_HOURS.value)
    await message.answer("How many hours did you sleep? (e.g. 7.5)")


@router.callback_query(QuickFlow.pick_value, F.data.startswith("quick:"))
async def quick_value_chosen(
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


@router.message(QuickFlow.pick_value)
async def quick_value_typed(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    """Fallback for sleep_hours and any case where the user types the value."""
    if message.text is None:
        return
    try:
        value = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Please send a number (e.g. 7 or 7.5).")
        return
    data = await state.get_data()
    metric = MetricType(data["metric"])
    svc = entry_service(session, cipher)
    dto = await svc.create(user, metric, value_numeric=value)
    await state.clear()
    await message.answer(
        f"Logged {METRIC_LABELS[metric]} = {value} for {dto.entry_date.isoformat()}."
    )
