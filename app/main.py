from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot, Dispatcher

from app.bot.handlers import register_all
from app.bot.middlewares.auth import AllowlistMiddleware
from app.bot.middlewares.context import ContextMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.user_ctx import UserContextMiddleware
from app.config import get_settings
from app.di import build_container
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.logging_setup import configure_logging
from app.services.analysis_service import AnalysisService
from app.services.anomaly_checkin_service import AnomalyCheckinService
from app.services.anomaly_detector import AnomalyDetector
from app.services.schedule_service import SummaryScheduler
from app.services.summary_service import SummaryService


def make_bot(token: str) -> Bot:
    # No default parse_mode: handlers send plain text. Setting HTML/Markdown
    # globally would break messages that contain literal angle brackets
    # (e.g. "<text>" placeholders in HELP_TEXT) or markdown-special chars.
    return Bot(token=token)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger("bot")

    container = build_container(settings)

    bot = make_bot(settings.bot_token)
    dp = Dispatcher(storage=container.fsm_storage)

    summary_service = SummaryService(
        ai_service=container.ai_service,
        sessionmaker=container.sessionmaker,
        cipher=container.cipher,
        chart_service=container.chart_service,
        pdf_service=container.pdf_service,
        bot=bot,
    )
    checkin_service = AnomalyCheckinService(
        sessionmaker=container.sessionmaker,
        schedule_repo_factory=SqlScheduleRepository,
        analysis_factory=lambda s: AnalysisService(SqlEntryRepository(s)),
        detector=AnomalyDetector(),
        bot=bot,
    )
    scheduler = SummaryScheduler(
        sessionmaker=container.sessionmaker,
        delivery=summary_service.send,
        allowed_telegram_ids=settings.allowed_telegram_ids,
        checkin_probe=checkin_service.maybe_probe,
    )

    # Order matters: outermost first.
    dp.update.outer_middleware(AllowlistMiddleware(settings.allowed_telegram_ids))
    dp.update.outer_middleware(ContextMiddleware(container))
    dp.update.outer_middleware(DbSessionMiddleware(container.sessionmaker))
    dp.update.outer_middleware(UserContextMiddleware(settings))

    register_all(dp)

    log.info("bot_starting", model=settings.anthropic_model)
    scheduler.start()
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    finally:
        await scheduler.stop()
        await container.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
