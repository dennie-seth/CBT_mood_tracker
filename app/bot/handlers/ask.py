from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import ToolDispatcher
from app.bot.deps import entry_service
from app.di import Container
from app.domain.models import User
from app.services.analysis_service import AnalysisService
from app.services.time import today_in_tz
from app.infrastructure.repositories.entry_repo import SqlEntryRepository

router = Router()


@router.message(Command("ask"))
async def cmd_ask(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    container: Container,
) -> None:
    if not command.args:
        await message.answer("Usage: /ask <question>")
        return

    repo = SqlEntryRepository(session)
    es = entry_service(session, container.cipher)
    analysis = AnalysisService(repo)

    dispatcher = ToolDispatcher(
        user_id=user.id,
        user_timezone=user.timezone,
        entry_service=es,
        analysis_service=analysis,
        chart_service=container.chart_service,
        pdf_service=container.pdf_service,
    )

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    today = today_in_tz(user.timezone)
    answer = await container.ai_service.answer(
        question=command.args.strip(),
        dispatcher=dispatcher,
        today=today,
    )

    if answer.text:
        await message.answer(answer.text)

    for art in answer.artifacts:
        file = BufferedInputFile(art.data, filename=art.filename)
        if art.kind == "image/png":
            await message.answer_photo(file)
        else:
            await message.answer_document(file)
