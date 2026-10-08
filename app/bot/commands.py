"""Telegram's "/" command menu, localized.

Global defaults: English, plus Russian for clients whose language is ru.
`/lang` additionally sets a chat-scoped menu so it follows the bot language
the user picked, not just their Telegram client's language.
"""
from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat

from app.bot.i18n import t

log = structlog.get_logger(__name__)

# Curated, most-used first. Rarely used commands stay in /help only.
MENU: tuple[str, ...] = (
    "mood", "anxiety", "migraine", "note", "thought", "today", "week", "ask",
    "log", "activate", "done", "chart", "migraines", "therapist",
    "home", "lang", "help", "cancel",
)


def menu_commands(lang: str) -> list[BotCommand]:
    return [BotCommand(command=c, description=t(lang, f"cmd.{c}")) for c in MENU]


async def setup_default_menu(bot: Bot) -> None:
    try:
        await bot.set_my_commands(menu_commands("en"))
        await bot.set_my_commands(menu_commands("ru"), language_code="ru")
    except TelegramAPIError as exc:  # the menu is a nicety; never block startup
        log.warning("set_commands_failed", error_type=type(exc).__name__)


async def set_chat_menu(bot: Bot, chat_id: int, lang: str) -> None:
    try:
        await bot.set_my_commands(menu_commands(lang), scope=BotCommandScopeChat(chat_id=chat_id))
    except TelegramAPIError as exc:
        log.warning("set_chat_commands_failed", error_type=type(exc).__name__)
