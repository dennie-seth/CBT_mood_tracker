from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
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
    daily = t(user.language, "sched.daily.off")
    weekly = t(user.language, "sched.weekly.off")
    if prefs:
        if prefs.daily_enabled and prefs.daily_at is not None:
            daily = t(
                user.language, "sched.daily.on",
                time=prefs.daily_at.strftime("%H:%M"),
                tz=user.timezone,
            )
        if (
            prefs.weekly_enabled
            and prefs.weekly_at is not None
            and prefs.weekly_weekday is not None
        ):
            weekly = t(
                user.language, "sched.weekly.on",
                dow=format_weekday(prefs.weekly_weekday),
                time=prefs.weekly_at.strftime("%H:%M"),
                tz=user.timezone,
            )
    await message.answer(
        t(user.language, "sched.show", daily=daily, weekly=weekly)
    )


@router.message(Command("dailyat"))
async def cmd_dailyat(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(t(user.language, "sched.dailyat.usage"))
        return
    try:
        at = parse_time(command.args.strip())
    except ValueError:
        await message.answer(
            t(user.language, "sched.dailyat.bad_time", raw=command.args.strip())
        )
        return
    repo = SqlScheduleRepository(session)
    await repo.set_daily(
        user.id, enabled=True, at=at, now_local=now_in_tz(user.timezone)
    )
    await message.answer(
        t(
            user.language, "sched.dailyat.set",
            time=at.strftime("%H:%M"), tz=user.timezone,
        )
    )


@router.message(Command("dailyoff"))
async def cmd_dailyoff(
    message: Message,
    user: User,
    session: AsyncSession,
) -> None:
    repo = SqlScheduleRepository(session)
    await repo.set_daily(user.id, enabled=False)
    await message.answer(t(user.language, "sched.dailyoff.set"))


@router.message(Command("weeklyat"))
async def cmd_weeklyat(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(t(user.language, "sched.weeklyat.usage"))
        return
    try:
        weekday, at = parse_weekly_args(command.args)
    except ValueError as e:
        msg = str(e)
        # Pick a more specific key when we recognise the failure shape.
        key = (
            "sched.weeklyat.bad_dow"
            if "weekday" in msg or "day" in msg
            else "sched.weeklyat.bad_time"
        )
        await message.answer(t(user.language, key, raw=command.args.strip()))
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
        t(
            user.language, "sched.weeklyat.set",
            dow=format_weekday(weekday),
            time=at.strftime("%H:%M"),
            tz=user.timezone,
        )
    )


@router.message(Command("weeklyoff"))
async def cmd_weeklyoff(
    message: Message,
    user: User,
    session: AsyncSession,
) -> None:
    repo = SqlScheduleRepository(session)
    await repo.set_weekly(user.id, enabled=False)
    await message.answer(t(user.language, "sched.weeklyoff.set"))
