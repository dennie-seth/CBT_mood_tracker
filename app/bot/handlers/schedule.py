from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.schedule_service import (
    format_weekday,
    parse_time,
    parse_weekly_args,
)
from app.services.time import now_in_tz

router = Router()


@router.message(Command("schedule"))
async def cmd_schedule(
    message: Message,
    user: User,
    session: AsyncSession,
) -> None:
    prefs = await SqlScheduleRepository(session).get(user.id)
    daily = "off"
    weekly = "off"
    if prefs:
        if prefs.daily_enabled and prefs.daily_at is not None:
            daily = f"on at {prefs.daily_at.strftime('%H:%M')}"
        if (
            prefs.weekly_enabled
            and prefs.weekly_at is not None
            and prefs.weekly_weekday is not None
        ):
            weekly = (
                f"on {format_weekday(prefs.weekly_weekday)} "
                f"at {prefs.weekly_at.strftime('%H:%M')}"
            )
    await message.answer(
        "Auto summaries:\n"
        f"• Daily: {daily}\n"
        f"• Weekly: {weekly}\n"
        f"\nTimes are interpreted in your timezone ({user.timezone}).\n"
        "Change with /dailyat HH:MM, /weeklyat <day> HH:MM, /dailyoff, /weeklyoff."
    )


@router.message(Command("dailyat"))
async def cmd_dailyat(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(
            "Usage: /dailyat 21:00\n"
            "Sets the time (your timezone) for the daily summary."
        )
        return
    try:
        at = parse_time(command.args.strip())
    except ValueError as e:
        await message.answer(f"Could not parse time: {e}")
        return
    repo = SqlScheduleRepository(session)
    await repo.set_daily(
        user.id, enabled=True, at=at, now_local=now_in_tz(user.timezone)
    )
    await message.answer(
        f"Daily summary enabled at {at.strftime('%H:%M')} ({user.timezone})."
    )


@router.message(Command("dailyoff"))
async def cmd_dailyoff(
    message: Message,
    user: User,
    session: AsyncSession,
) -> None:
    repo = SqlScheduleRepository(session)
    await repo.set_daily(user.id, enabled=False)
    await message.answer("Daily summary disabled.")


@router.message(Command("weeklyat"))
async def cmd_weeklyat(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(
            "Usage: /weeklyat sun 21:00\n"
            "Sets the day & time (your timezone) for the weekly summary.\n"
            "Days: mon, tue, wed, thu, fri, sat, sun."
        )
        return
    try:
        weekday, at = parse_weekly_args(command.args)
    except ValueError as e:
        await message.answer(f"Could not parse: {e}")
        return
    repo = SqlScheduleRepository(session)
    await repo.set_weekly(
        user.id,
        enabled=True,
        weekday=weekday,
        at=at,
        now_local=now_in_tz(user.timezone),
    )
    await message.answer(
        f"Weekly summary enabled on {format_weekday(weekday)} "
        f"at {at.strftime('%H:%M')} ({user.timezone})."
    )


@router.message(Command("weeklyoff"))
async def cmd_weeklyoff(
    message: Message,
    user: User,
    session: AsyncSession,
) -> None:
    repo = SqlScheduleRepository(session)
    await repo.set_weekly(user.id, enabled=False)
    await message.answer("Weekly summary disabled.")
