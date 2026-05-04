from __future__ import annotations

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
from app.services.time import parse_period

router = Router()


async def _send_pdf(
    chat_id: int,
    bot,
    user: User,
    session: AsyncSession,
    container: Container,
    period: str,
) -> None:
    try:
        start, end = parse_period(period, user.timezone)
    except ValueError as e:
        await bot.send_message(chat_id, str(e))
        return

    analysis = AnalysisService(SqlEntryRepository(session))
    df = await analysis.daily_summary(user.id, start, end)
    pdf = container.pdf_service.report(df, start=start, end=end)
    file = BufferedInputFile(pdf, filename=f"report_{start}_{end}.pdf")
    await bot.send_document(
        chat_id, file,
        caption=t(
            user.language, "export.caption",
            start=start.isoformat(), end=end.isoformat(),
        ),
    )


@router.message(Command("export"))
async def cmd_export(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if not command.args:
        await message.answer(
            t(user.language, "export.pick_period"),
            reply_markup=period_picker("export"),
        )
        return
    await _send_pdf(
        message.chat.id, message.bot, user, session, container, command.args.strip().split()[0]
    )


@router.callback_query(F.data.startswith("export:"))
async def export_picked(
    cb: CallbackQuery,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if cb.data is None or cb.message is None:
        return
    period = cb.data.split(":", 1)[1]
    await _send_pdf(cb.message.chat.id, cb.bot, user, session, container, period)
    await cb.answer()
