"""/hide, /pause, /tidy handlers, and auto-tidy hooks on notes / thoughts."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import journal, privacy
from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.entry_service import EntryService
from tests.unit.fakes import FakeEntryRepo

_ids = iter(range(1000, 100_000))


@pytest.fixture()
async def user(schedule_sm) -> User:
    async with schedule_sm() as s:
        u = User(id=42, telegram_id=1, display_name="t", timezone="UTC", language="en")
        s.add(u)
        await s.commit()
        return u


@pytest.fixture()
def state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


def _msg(text: str = "") -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.message_id = next(_ids)
    m.bot = AsyncMock()
    reply = MagicMock(spec=Message)
    reply.message_id = next(_ids)
    m.answer = AsyncMock(return_value=reply)
    m.edit_text = AsyncMock()
    return m


def _cb(data: str) -> MagicMock:
    c = MagicMock(spec=CallbackQuery)
    c.data = data
    c.message = _msg()
    c.bot = c.message.bot
    c.answer = AsyncMock()
    return c


def _kb(call) -> list[str]:
    kb = call.kwargs.get("reply_markup")
    return [b.callback_data for row in kb.inline_keyboard for b in row] if kb else []


# --- /hide -----------------------------------------------------------------

async def test_hide_asks_first(user, state, schedule_sm) -> None:
    m = _msg("/hide")
    await privacy.cmd_hide(m, user)
    assert {"hide:yes", "hide:no"} <= set(_kb(m.answer.await_args))


async def test_hide_yes_clears_chat(user, state, schedule_sm, monkeypatch) -> None:
    clear = AsyncMock(return_value=12)
    monkeypatch.setattr(privacy, "clear_chat", clear)
    c = _cb("hide:yes")
    await privacy.on_hide(c, user, MagicMock(sessionmaker=schedule_sm))
    assert clear.await_args.kwargs["chat_id"] == 1
    assert "still saved" in c.message.answer.await_args.args[0]


async def test_hide_no_does_nothing(user, state, schedule_sm, monkeypatch) -> None:
    clear = AsyncMock()
    monkeypatch.setattr(privacy, "clear_chat", clear)
    c = _cb("hide:no")
    await privacy.on_hide(c, user, MagicMock(sessionmaker=schedule_sm))
    clear.assert_not_awaited()


# --- /pause ------------------------------------------------------------------

async def _paused(sm) -> set[int]:
    async with sm() as s:
        return await SqlScheduleRepository(s).paused_user_ids(datetime.now(tz=UTC))


@pytest.mark.parametrize("args,days", [("3d", 3), ("3", 3), ("1д", 1), ("14d", 14)])
async def test_pause_with_args(user, schedule_sm, args, days) -> None:
    async with schedule_sm() as s:
        m = _msg(f"/pause {args}")
        await privacy.cmd_pause(m, MagicMock(args=args), user, s)
        await s.commit()
        prefs = await SqlScheduleRepository(s).get(user.id)
    until = prefs.paused_until if prefs.paused_until.tzinfo else prefs.paused_until.replace(tzinfo=UTC)
    assert timedelta(days=days) - timedelta(minutes=1) < until - datetime.now(tz=UTC) <= timedelta(days=days)
    assert "Paused until" in m.answer.await_args.args[0]


async def test_pause_buttons_and_resume(user, schedule_sm) -> None:
    async with schedule_sm() as s:
        m = _msg("/pause")
        await privacy.cmd_pause(m, MagicMock(args=None), user, s)
        assert {"pause:1", "pause:3", "pause:7"} <= set(_kb(m.answer.await_args))
        await privacy.on_pause(_cb("pause:7"), user, s)
        await s.commit()
    assert await _paused(schedule_sm) == {42}
    async with schedule_sm() as s:
        m = _msg("/pause off")
        await privacy.cmd_pause(m, MagicMock(args="off"), user, s)
        await s.commit()
    assert await _paused(schedule_sm) == set()
    assert "Resumed" in m.answer.await_args.args[0]


@pytest.mark.parametrize("args", ["0d", "30d", "soon"])
async def test_pause_rejects_bad_args(user, schedule_sm, args) -> None:
    async with schedule_sm() as s:
        m = _msg(f"/pause {args}")
        await privacy.cmd_pause(m, MagicMock(args=args), user, s)
    assert "/pause 1d" in m.answer.await_args.args[0]
    assert await _paused(schedule_sm) == set()


# --- /tidy + hooks -------------------------------------------------------------

async def test_tidy_on_off(user, schedule_sm) -> None:
    async with schedule_sm() as s:
        m = _msg("/tidy on")
        await privacy.cmd_tidy(m, MagicMock(args="on"), user, s)
        await s.commit()
        assert await SqlScheduleRepository(s).tidy_enabled(user.id) is True
        await privacy.cmd_tidy(_msg("/tidy off"), MagicMock(args="off"), user, s)
        await s.commit()
        assert await SqlScheduleRepository(s).tidy_enabled(user.id) is False


async def test_note_saved_hands_its_span_to_tidy(user, state, cipher, monkeypatch) -> None:
    repo = FakeEntryRepo()
    monkeypatch.setattr(journal, "entry_service", lambda s, c: EntryService(repo, cipher))
    tidy = AsyncMock()
    monkeypatch.setattr(journal, "maybe_tidy", tidy)

    m = _msg("/note feeling raw today")
    await journal.cmd_note(m, MagicMock(args="feeling raw today"), state, user, None, cipher)

    kw = tidy.await_args.kwargs
    assert kw["first_id"] == m.message_id
    assert kw["last_id"] == m.answer.return_value.message_id


async def test_thought_record_span_starts_at_command(user, state, cipher, monkeypatch) -> None:
    repo = FakeEntryRepo()
    monkeypatch.setattr(journal, "entry_service", lambda s, c: EntryService(repo, cipher))
    tidy = AsyncMock()
    monkeypatch.setattr(journal, "maybe_tidy", tidy)

    start = _msg("/thought")
    await journal.cmd_thought(start, state, user)
    await journal.thought_situation(_msg("meeting"), state, user)
    await journal.thought_auto(_msg("they hate me"), state, user)
    await journal.thought_distortion(_msg("mind reading"), state, user)
    end = _msg("maybe they were busy")
    await journal.thought_reframe(end, state, user, None, cipher)

    kw = tidy.await_args.kwargs
    assert kw["first_id"] == start.message_id
    assert kw["last_id"] == end.answer.return_value.message_id
