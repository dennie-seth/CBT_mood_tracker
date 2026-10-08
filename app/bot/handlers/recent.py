"""/recent — latest entries with fix / delete.

`rc:<action>:<id>[:<arg>]` buttons; every action re-loads the entry through
EntryService with an ownership check, so a forged id for another user's
entry just gets "can't find it". Entry text is shown to the user, never
put in callback data.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import metric_label, t
from app.bot.migraine_card import fmt_when, summary_line
from app.bot.states import RecentFlow
from app.domain.enums import NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import EntryDTO, EntryService
from app.services.time import today_in_tz

router = Router()
log = structlog.get_logger(__name__)

LIMIT = 12
_NOT_A_COMMAND = ~F.text.startswith("/")


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _value(e: EntryDTO, user: User) -> str:
    if e.metric_type is MetricType.MIGRAINE:
        return summary_line(e, user.language, user.timezone, datetime.now(tz=UTC))
    if e.value_numeric is not None:
        return _fmt(e.value_numeric)
    if e.value_text:
        return e.value_text
    extra = e.extra or {}
    return " | ".join(str(v) for k, v in extra.items() if k.endswith("_text") and v) or "—"


def _when(e: EntryDTO, user: User) -> str:
    return fmt_when(e.recorded_at.isoformat(), user.language, user.timezone, datetime.now(tz=UTC))


async def _list(user: User, es: EntryService) -> tuple[str, InlineKeyboardMarkup | None]:
    end = today_in_tz(user.timezone)
    rows = await es.list_range(user.id, end - timedelta(days=30), end)
    rows = sorted(rows, key=lambda e: (e.recorded_at, e.id), reverse=True)[:LIMIT]
    if not rows:
        return t(user.language, "recent.empty"), None
    buttons = []
    for e in rows:
        label = f"{metric_label(e.metric_type, user.language)}: {_value(e, user)}"
        label = label if len(label) <= 44 else label[:43] + "…"
        buttons.append([_btn(f"{label} · {_when(e, user)}", f"rc:open:{e.id}")])
    return t(user.language, "recent.header"), InlineKeyboardMarkup(inline_keyboard=buttons)


def _detail(e: EntryDTO, user: User) -> tuple[str, InlineKeyboardMarkup]:
    lang = user.language
    text = f"{metric_label(e.metric_type, lang)}\n{_when(e, user)}\n\n{_value(e, user)}"
    rows: list[list[InlineKeyboardButton]] = []
    if e.metric_type is MetricType.MIGRAINE:
        rows.append([_btn(t(lang, "recent.btn.card"), f"mg:card:{e.id}")])
    else:
        if e.metric_type in NUMERIC_METRICS:
            rows.append([_btn(t(lang, "recent.btn.value"), f"rc:val:{e.id}")])
        elif e.value_text:
            rows.append([_btn(t(lang, "recent.btn.text"), f"rc:txt:{e.id}")])
        rows.append([_btn(t(lang, "recent.btn.delete"), f"rc:del:{e.id}")])
    rows.append([_btn(t(lang, "recent.btn.back"), "rc:list:0")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("recent"))
async def cmd_recent(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    await state.clear()
    text, kb = await _list(user, entry_service(session, cipher))
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("rc:"))
async def on_recent(
    cb: CallbackQuery, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    lang = user.language
    parts = (cb.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    msg = cb.message if isinstance(cb.message, Message) else None
    es = entry_service(session, cipher)
    await state.clear()

    if action == "list":
        list_text, list_kb = await _list(user, es)
        if msg:
            await msg.edit_text(list_text, reply_markup=list_kb)
        await cb.answer()
        return

    kb: InlineKeyboardMarkup | None
    try:
        entry_id = int(parts[2])
        entry = await es.get_for_user(entry_id, user)
        if entry is None:
            raise LookupError(entry_id)
        if action == "open":
            text, kb = _detail(entry, user)
        elif action == "val":
            if entry.metric_type is MetricType.SLEEP_HOURS:
                await state.set_state(RecentFlow.edit_text)
                await state.set_data({"entry_id": entry_id, "kind": "number"})
                text, kb = t(lang, "log.enter_sleep_hours"), None
            else:
                rows = [
                    [_btn(str(n), f"rc:set:{entry_id}:{n}") for n in rng]
                    for rng in (range(1, 6), range(6, 11))
                ]
                rows.append([_btn(t(lang, "recent.btn.back"), f"rc:open:{entry_id}")])
                text = t(lang, "recent.pick_value", label=metric_label(entry.metric_type, lang))
                kb = InlineKeyboardMarkup(inline_keyboard=rows)
        elif action == "set":
            entry = await es.update_value(entry_id, user, value_numeric=float(int(parts[3])))
            text, kb = _detail(entry, user)
        elif action == "txt":
            await state.set_state(RecentFlow.edit_text)
            await state.set_data({"entry_id": entry_id, "kind": "text"})
            text, kb = t(lang, "recent.ask_text"), None
        elif action == "del":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [_btn(t(lang, "recent.btn.delete_yes"), f"rc:dely:{entry_id}")],
                [_btn(t(lang, "recent.btn.back"), f"rc:open:{entry_id}")],
            ])
            text = t(lang, "recent.ask_delete")
        elif action == "dely":
            await es.delete_for_user(entry_id, user)
            log.info("entry_deleted_from_recent", entry_id=entry_id)
            text, kb = t(lang, "recent.deleted"), None
        else:
            await cb.answer(t(lang, "stale.button"))
            return
    except (IndexError, ValueError, LookupError, PermissionError) as exc:
        log.info("recent_action_failed", action=action, error_type=type(exc).__name__)
        await cb.answer(t(lang, "recent.not_found"), show_alert=True)
        return
    if msg:
        await msg.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.message(RecentFlow.edit_text, F.text, _NOT_A_COMMAND)
async def recent_text_typed(
    message: Message, state: FSMContext, user: User,
    session: AsyncSession, cipher: FernetCipher,
) -> None:
    data = await state.get_data()
    es = entry_service(session, cipher)
    raw = (message.text or "").strip()
    is_number = data.get("kind") == "number"
    try:
        if is_number:
            entry = await es.update_value(
                int(data["entry_id"]), user, value_numeric=float(raw.replace(",", "."))
            )
        else:
            entry = await es.update_value(int(data["entry_id"]), user, value_text=raw)
    except (LookupError, PermissionError):
        await state.clear()
        await message.answer(t(user.language, "recent.not_found"))
        return
    except ValueError:
        await message.answer(t(user.language, "err.send_number" if is_number else "err.send_text"))
        return
    await state.clear()
    text, kb = _detail(entry, user)
    await message.answer(f"{t(user.language, 'recent.saved')}\n\n{text}", reply_markup=kb)
