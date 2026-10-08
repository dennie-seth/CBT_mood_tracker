"""Buttons under "logged ✓" confirmations: Undo / Add a note / Thought record.

`en:undo:<id,id,…>` deletes exactly those entries through
`EntryService.delete_for_user`, which re-checks ownership — a forged id for
someone else's entry is refused.
"""
from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import t
from app.bot.states import JournalFlow, ThoughtFlow
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher

router = Router()
log = structlog.get_logger(__name__)


@router.callback_query(F.data.startswith("en:"))
async def on_entry_action(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    parts = (cb.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    lang = user.language

    if action == "undo":
        try:
            ids = [int(i) for i in parts[2].split(",")]
            svc = entry_service(session, cipher)
            for entry_id in ids:
                await svc.delete_for_user(entry_id, user)
        except (IndexError, ValueError, LookupError, PermissionError) as exc:
            log.info("entry_undo_failed", error_type=type(exc).__name__)
            await cb.answer(t(lang, "entry.undo_failed"), show_alert=True)
            return
        log.info("entry_undone", count=len(ids))
        if isinstance(cb.message, Message):
            await cb.message.edit_text(t(lang, "entry.undone"))
        await cb.answer()
        return

    if action == "note":
        await state.clear()
        await state.set_state(JournalFlow.enter_text)
        if isinstance(cb.message, Message):
            prompt = await cb.message.answer(t(lang, "entry.note_prompt"))
            await state.set_data({"first_id": prompt.message_id})
        await cb.answer()
        return

    if action == "thought":
        await state.clear()
        await state.set_state(ThoughtFlow.situation)
        if isinstance(cb.message, Message):
            prompt = await cb.message.answer(t(lang, "thought.start"))
            await state.set_data({"first_id": prompt.message_id})
        await cb.answer()
        return

    await cb.answer()
