from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository

router = Router()


@router.message(Command("checkins"))
async def cmd_checkins(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    repo = SqlScheduleRepository(session)
    if not command.args:
        prefs = await repo.get(user.id)
        on = bool(prefs and prefs.checkins_enabled)
        await message.answer(
            t(user.language, "checkins.show.on" if on else "checkins.show.off")
        )
        return

    arg = command.args.strip().lower()
    if arg == "on":
        await repo.set_checkins(user.id, enabled=True)
        await message.answer(t(user.language, "checkins.set.on"))
        return
    if arg == "off":
        await repo.set_checkins(user.id, enabled=False)
        await message.answer(t(user.language, "checkins.set.off"))
        return
    await message.answer(t(user.language, "checkins.unknown"))
