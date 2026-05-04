from __future__ import annotations

import pytz
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.domain.models import User
from app.infrastructure.repositories.user_repo import SqlUserRepository

router = Router()


@router.message(Command("tz"))
async def cmd_tz(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(t(user.language, "tz.usage"))
        return
    tz_name = command.args.strip()
    try:
        pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        await message.answer(t(user.language, "tz.unknown", raw=tz_name))
        return
    repo = SqlUserRepository(session)
    await repo.update_timezone(user.id, tz_name)
    user.timezone = tz_name
    await message.answer(t(user.language, "tz.saved", tz=tz_name))
