from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import period_picker
from app.di import Container
from app.domain.models import User
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.services.entry_service import EntryService
from app.services.therapist_export_service import TherapistExportService
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

    es = EntryService(SqlEntryRepository(session), container.cipher)
    svc = TherapistExportService(es)
    data = await svc.collect(user, start=start, end=end)
    pdf = container.pdf_service.therapist_report(
        data, user=user, start=start, end=end
    )
    file = BufferedInputFile(
        pdf, filename=f"therapist_report_{start}_{end}.pdf"
    )
    await bot.send_document(
        chat_id, file,
        caption=(
            f"Therapist report {start.isoformat()} → {end.isoformat()}.\n"
            "Includes thought records, BA outcomes and notes — share with your "
            "clinician only."
        ),
    )


@router.message(Command("therapist"))
async def cmd_therapist(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if not command.args:
        await message.answer(
            "Pick a period for the therapist report:",
            reply_markup=period_picker("therapist"),
        )
        return
    await _send_pdf(
        message.chat.id, message.bot, user, session, container,
        command.args.strip().split()[0],
    )


@router.callback_query(F.data.startswith("therapist:"))
async def therapist_picked(
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
