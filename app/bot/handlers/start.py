from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.home import build_home_keyboard
from app.bot.i18n import EN, t
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()

# Re-export the English help body so other modules / tests that just
# want to introspect the canonical command list don't have to know the
# i18n key.
HELP_TEXT = EN["help.text"]


@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User, session: AsyncSession, cipher: FernetCipher
) -> None:
    name = user.display_name or "there"
    greeting = t(user.language, "start.hi", name=name)
    await message.answer(
        greeting + t(user.language, "help.text"),
        reply_markup=await build_home_keyboard(user, session, cipher),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    await message.answer(t(user.language, "help.text"))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state, user: User) -> None:  # type: ignore[no-untyped-def]
    await state.clear()
    await message.answer(t(user.language, "cancel.done"))
