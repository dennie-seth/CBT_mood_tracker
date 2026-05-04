from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import register_all
from app.bot.middlewares.auth import AllowlistMiddleware
from app.bot.middlewares.context import ContextMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.user_ctx import UserContextMiddleware
from app.config import get_settings
from app.di import build_container
from app.logging_setup import configure_logging


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger("bot")

    container = build_container(settings)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: outermost first.
    dp.update.outer_middleware(AllowlistMiddleware(settings.allowed_telegram_ids))
    dp.update.outer_middleware(ContextMiddleware(container))
    dp.update.outer_middleware(DbSessionMiddleware(container.sessionmaker))
    dp.update.outer_middleware(UserContextMiddleware(settings))

    register_all(dp)

    log.info("bot_starting", model=settings.anthropic_model)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    finally:
        await container.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
