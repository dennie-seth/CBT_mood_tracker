from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.chat_cleanup import maybe_tidy
from app.bot.deps import entry_service
from app.bot.i18n import t
from app.bot.keyboards import entry_actions
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
        reply = await message.answer(
            t(user.language, "note.saved", date=dto.entry_date.isoformat()),
            reply_markup=entry_actions(user.language, [dto.id]),
        )
        await maybe_tidy(message.bot, session, user, chat_id=message.chat.id,
                         first_id=message.message_id, last_id=reply.message_id)
        return
    await state.set_state(JournalFlow.enter_text)
    await state.set_data({"first_id": message.message_id})
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
    first_id = (await state.get_data()).get("first_id", message.message_id)
    await state.clear()
    reply = await message.answer(
        t(user.language, "note.saved", date=dto.entry_date.isoformat()),
        reply_markup=entry_actions(user.language, [dto.id]),
    )
    await maybe_tidy(message.bot, session, user, chat_id=message.chat.id,
                     first_id=first_id, last_id=reply.message_id)


@router.message(Command("thought"))
async def cmd_thought(message: Message, state: FSMContext, user: User) -> None:
    await state.set_state(ThoughtFlow.situation)
    await state.set_data({"first_id": message.message_id})
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
    await message.answer(
        t(user.language, "thought.ask_distortion"),
        reply_markup=_distortion_keyboard(user.language),
    )


DISTORTIONS: tuple[str, ...] = (
    "catastrophising", "all_or_nothing", "mind_reading", "fortune_telling",
    "personalisation", "overgeneralisation", "labelling", "shoulds",
    "emotional_reasoning", "discounting_positive",
)


def _distortion_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=t(lang, f"dist.{k}"), callback_data=f"td:{k}")
        for k in DISTORTIONS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text=t(lang, "dist.other"), callback_data="td:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(ThoughtFlow.distortion, F.data.startswith("td:"))
async def distortion_tapped(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    key = (cb.data or "").split(":", 1)[1]
    msg = cb.message if isinstance(cb.message, Message) else None
    if key == "other" or key not in DISTORTIONS:
        if msg:
            await msg.edit_text(t(user.language, "thought.type_distortion"))
        await cb.answer()
        return  # stay in ThoughtFlow.distortion; the typed handler takes it
    label = t(user.language, f"dist.{key}")
    await state.update_data(distortion_text=label)
    await state.set_state(ThoughtFlow.reframe)
    if msg:
        await msg.edit_text(f"✓ {label}\n\n{t(user.language, 'thought.ask_reframe')}")
    await cb.answer()


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
    reply = await message.answer(
        t(user.language, "thought.saved", date=dto.entry_date.isoformat())
    )
    await maybe_tidy(message.bot, session, user, chat_id=message.chat.id,
                     first_id=data.get("first_id", message.message_id), last_id=reply.message_id)
