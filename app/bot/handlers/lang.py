from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import SUPPORTED, t
from app.domain.models import User
from app.infrastructure.repositories.user_repo import SqlUserRepository

router = Router()


@router.message(Command("lang"))
async def cmd_lang(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
) -> None:
    if not command.args:
        await message.answer(t(user.language, "lang.help"))
        return
    code = command.args.strip().lower().split()[0]
    if code not in SUPPORTED:
        await message.answer(t(user.language, "lang.unknown", code=code))
        return
    await SqlUserRepository(session).update_language(user.id, code)
    user.language = code  # so the confirmation goes out in the new language
    await message.answer(t(code, "lang.set"))
