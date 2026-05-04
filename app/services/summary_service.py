from __future__ import annotations

from datetime import date
from typing import Literal

import structlog
from aiogram import Bot
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.summary_prompts import DAILY_PROMPT, WEEKLY_PROMPT
from app.ai.tools import ToolDispatcher
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.ai_service import AiService
from app.services.analysis_service import AnalysisService
from app.services.chart_service import ChartService
from app.services.entry_service import EntryService
from app.services.pdf_service import PdfService

log = structlog.get_logger(__name__)

SummaryKind = Literal["daily", "weekly"]


class SummaryService:
    """Per-user proactive summary delivery via Haiku.

    Mirrors the /ask handler's wiring (ToolDispatcher + AiService.answer +
    artifact forwarding) but runs on its own AsyncSession (no aiogram
    middleware in scope) and stamps the schedule's last-sent date on success.
    On failure, last-sent stays untouched so the next tick retries.
    """

    def __init__(
        self,
        ai_service: AiService,
        sessionmaker: async_sessionmaker[AsyncSession],
        cipher: FernetCipher,
        chart_service: ChartService,
        pdf_service: PdfService,
        bot: Bot,
    ) -> None:
        self._ai = ai_service
        self._sm = sessionmaker
        self._cipher = cipher
        self._chart = chart_service
        self._pdf = pdf_service
        self._bot = bot

    async def send(self, user: User, *, kind: SummaryKind, local_today: date) -> None:
        async with self._sm() as session:
            entry_repo = SqlEntryRepository(session)
            entry_service = EntryService(entry_repo, self._cipher)
            analysis_service = AnalysisService(entry_repo)
            dispatcher = ToolDispatcher(
                user_id=user.id,
                user_timezone=user.timezone,
                entry_service=entry_service,
                analysis_service=analysis_service,
                chart_service=self._chart,
                pdf_service=self._pdf,
            )

            prompt = DAILY_PROMPT if kind == "daily" else WEEKLY_PROMPT
            answer = await self._ai.answer(
                question=prompt, dispatcher=dispatcher, today=local_today
            )

            if answer.text:
                await self._bot.send_message(
                    chat_id=user.telegram_id, text=answer.text
                )
            for art in answer.artifacts:
                file = BufferedInputFile(art.data, filename=art.filename)
                if art.kind == "image/png":
                    await self._bot.send_photo(chat_id=user.telegram_id, photo=file)
                else:
                    await self._bot.send_document(
                        chat_id=user.telegram_id, document=file
                    )

            schedule_repo = SqlScheduleRepository(session)
            if kind == "daily":
                await schedule_repo.stamp_daily_sent(user.id, on=local_today)
            else:
                await schedule_repo.stamp_weekly_sent(user.id, on=local_today)
            await session.commit()

            log.info(
                "summary_sent",
                user_id=user.id,
                kind=kind,
                local_date=local_today.isoformat(),
                artifact_count=len(answer.artifacts),
            )
