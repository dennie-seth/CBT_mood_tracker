from __future__ import annotations

from datetime import date

import pandas as pd
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.bot.keyboards import period_picker
from app.di import Container
from app.domain.models import User
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.services.analysis_service import AnalysisService
from app.services.time import parse_period, today_in_tz

router = Router()


async def _send_chart(
    message_or_cb: Message | CallbackQuery,
    user: User,
    session: AsyncSession,
    container: Container,
    period: str,
) -> None:
    chat = (
        message_or_cb.message.chat
        if isinstance(message_or_cb, CallbackQuery) and message_or_cb.message
        else message_or_cb.chat  # type: ignore[union-attr]
    )
    bot = message_or_cb.bot
    assert bot is not None

    try:
        start, end = parse_period(period, user.timezone)
    except ValueError as e:
        await bot.send_message(chat.id, str(e))
        return

    analysis = AnalysisService(SqlEntryRepository(session))
    df = await analysis.daily_summary(user.id, start, end)
    png = container.chart_service.line(df)
    file = BufferedInputFile(png, filename=f"chart_{start}_{end}.png")
    await bot.send_photo(
        chat.id, file, caption=f"{start.isoformat()} → {end.isoformat()}"
    )


@router.message(Command("chart"))
async def cmd_chart(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if not command.args:
        await message.answer(
            t(user.language, "chart.pick_period"),
            reply_markup=period_picker("chart"),
        )
        return
    await _send_chart(
        message, user, session, container, command.args.strip().split()[0]
    )


@router.callback_query(F.data.startswith("chart:"))
async def chart_picked(
    cb: CallbackQuery,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if cb.data is None:
        return
    period = cb.data.split(":", 1)[1]
    await _send_chart(cb, user, session, container, period)
    await cb.answer()


# --- /pixels -------------------------------------------------------------------

async def _daily_summary(
    user: User, session: AsyncSession, start: date, end: date
) -> pd.DataFrame:
    return await AnalysisService(SqlEntryRepository(session)).daily_summary(user.id, start, end)


@router.message(Command("pixels"))
async def cmd_pixels(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    today = today_in_tz(user.timezone)
    raw = (command.args or "").strip()
    try:
        year = int(raw) if raw else today.year
    except ValueError:
        year = 0
    if not 2000 <= year <= today.year:
        await message.answer(t(user.language, "pixels.bad_year", year=today.year))
        return
    start, end = date(year, 1, 1), date(year, 12, 31)
    df = await _daily_summary(user, session, start, end)
    png = container.chart_service.year_pixels(df, year=year, today=today)
    mood_days = int(df["mood"].notna().sum()) if "mood" in df.columns else 0
    migraine_days = int(df["migraine"].notna().sum()) if "migraine" in df.columns else 0
    await message.answer_photo(
        BufferedInputFile(png, filename=f"mood_{year}.png"),
        caption=t(user.language, "pixels.caption", year=year,
                  days=mood_days, migraines=migraine_days),
    )
