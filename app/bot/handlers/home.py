"""/home and the persistent shortcut keyboard.

Registered right after /start so a shortcut tap works even mid-flow (it
would otherwise be swallowed as e.g. note text); each tap clears any
pending step first.
"""
from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.handlers import migraine, today
from app.bot.handlers.ask import run_ask
from app.bot.home import home_keyboard, resolve_home_button, top_quick_metrics
from app.bot.i18n import metric_label, t
from app.bot.keyboards import scale_1_to_10
from app.bot.states import AskFlow, JournalFlow, QuickFlow
from app.di import Container
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.time import today_in_tz

router = Router()


async def build_home_keyboard(
    user: User, session: AsyncSession, cipher: FernetCipher
) -> ReplyKeyboardMarkup:
    end = today_in_tz(user.timezone)
    rows = await entry_service(session, cipher).list_range(user.id, end - timedelta(days=30), end)
    return home_keyboard(user.language, top_quick_metrics(rows))


@router.message(Command("home"))
async def cmd_home(
    message: Message, command: CommandObject, user: User,
    session: AsyncSession, container: Container,
) -> None:
    if (command.args or "").strip().lower() == "off":
        await message.answer(t(user.language, "home.hidden"), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        t(user.language, "home.shown"),
        reply_markup=await build_home_keyboard(user, session, container.cipher),
    )


@router.message(F.text.func(resolve_home_button))
async def home_button(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, container: Container,
) -> None:
    action = resolve_home_button(message.text)
    if action is None:
        return
    await state.clear()
    lang = user.language
    if action.kind == "metric" and action.metric is not None:
        await state.set_state(QuickFlow.pick_value)
        await state.update_data(metric=action.metric.value)
        await message.answer(
            t(lang, "log.enter_numeric", label=metric_label(action.metric, lang)),
            reply_markup=scale_1_to_10(callback_prefix="quick"),
        )
    elif action.kind == "note":
        await state.set_state(JournalFlow.enter_text)
        await message.answer(t(lang, "note.send"))
    elif action.kind == "ask":
        await state.set_state(AskFlow.question)
        await message.answer(t(lang, "home.ask_question"))
    elif action.kind == "migraine":
        await migraine.cmd_migraine(message, state, user, session, container.cipher)
    elif action.kind == "today":
        await today.cmd_today(message, user, session, container.cipher)


@router.message(AskFlow.question, F.text, ~F.text.startswith("/"))
async def ask_question_typed(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, container: Container,
) -> None:
    await state.clear()
    await run_ask(
        message, question=(message.text or "").strip(), user=user,
        session=session, container=container,
    )
