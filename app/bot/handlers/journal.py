from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import t
from app.bot.states import JournalFlow, ThoughtFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()


@router.message(Command("note"))
async def cmd_note(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if command.args:
        svc = entry_service(session, cipher)
        dto = await svc.create(user, MetricType.NOTE, value_text=command.args.strip())
        await message.answer(
            t(user.language, "note.saved", date=dto.entry_date.isoformat())
        )
        return
    await state.set_state(JournalFlow.enter_text)
    await message.answer(t(user.language, "note.send"))


@router.message(JournalFlow.enter_text)
async def journal_text(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if not message.text:
        await message.answer(t(user.language, "err.send_text"))
        return
    svc = entry_service(session, cipher)
    dto = await svc.create(user, MetricType.NOTE, value_text=message.text.strip())
    await state.clear()
    await message.answer(
        t(user.language, "note.saved", date=dto.entry_date.isoformat())
    )


@router.message(Command("thought"))
async def cmd_thought(message: Message, state: FSMContext, user: User) -> None:
    await state.set_state(ThoughtFlow.situation)
    await message.answer(t(user.language, "thought.start"))


@router.message(ThoughtFlow.situation)
async def thought_situation(message: Message, state: FSMContext, user: User) -> None:
    if not message.text:
        return
    await state.update_data(situation_text=message.text.strip())
    await state.set_state(ThoughtFlow.automatic_thought)
    await message.answer(t(user.language, "thought.ask_auto"))


@router.message(ThoughtFlow.automatic_thought)
async def thought_auto(message: Message, state: FSMContext, user: User) -> None:
    if not message.text:
        return
    await state.update_data(automatic_thought_text=message.text.strip())
    await state.set_state(ThoughtFlow.distortion)
    await message.answer(t(user.language, "thought.ask_distortion"))


@router.message(ThoughtFlow.distortion)
async def thought_distortion(message: Message, state: FSMContext, user: User) -> None:
    if not message.text:
        return
    await state.update_data(distortion_text=message.text.strip())
    await state.set_state(ThoughtFlow.reframe)
    await message.answer(t(user.language, "thought.ask_reframe"))


@router.message(ThoughtFlow.reframe)
async def thought_reframe(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if not message.text:
        return
    data = await state.get_data()
    extra = {
        "situation_text": data.get("situation_text", ""),
        "automatic_thought_text": data.get("automatic_thought_text", ""),
        "distortion_text": data.get("distortion_text", ""),
        "reframe_text": message.text.strip(),
    }
    svc = entry_service(session, cipher)
    dto = await svc.create(user, MetricType.THOUGHT_RECORD, extra=extra)
    await state.clear()
    await message.answer(
        t(user.language, "thought.saved", date=dto.entry_date.isoformat())
    )
