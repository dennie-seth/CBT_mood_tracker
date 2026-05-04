from __future__ import annotations

import pytz
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

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
        await message.answer(
            f"Your timezone is {user.timezone}. To change: /tz Europe/Berlin"
        )
        return
    tz_name = command.args.strip()
    try:
        pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        await message.answer(f"Unknown timezone: {tz_name}. Use an IANA name like 'Europe/Berlin'.")
        return
    repo = SqlUserRepository(session)
    await repo.update_timezone(user.id, tz_name)
    user.timezone = tz_name  # update the in-memory copy for this request
    await message.answer(f"Timezone set to {tz_name}.")
