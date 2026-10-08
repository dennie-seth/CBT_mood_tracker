"""Everyday friction: plain text, one-message logging, Undo / add-context
buttons on confirmations, and the home keyboard.

Handlers are driven directly (MagicMock Telegram objects, real FSMContext
over MemoryStorage, EntryService over the shared fake repo).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import entry_actions, home, plain, quick
from app.bot.states import AskFlow, JournalFlow, PlainTextFlow, QuickFlow, ThoughtFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryService
from tests.unit.fakes import FakeEntryRepo

_ids = iter(range(1000, 100_000))


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC", language="en")
    u.id = 42
    return u


@pytest.fixture()
def state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.fixture()
def repo(monkeypatch, cipher) -> FakeEntryRepo:
    r = FakeEntryRepo()
    make = lambda session, c: EntryService(r, cipher)  # noqa: E731
    for mod in (entry_actions, home, plain, quick):
        monkeypatch.setattr(mod, "entry_service", make)
    return r


@pytest.fixture()
def container(cipher) -> MagicMock:
    return MagicMock(cipher=cipher)


@pytest.fixture()
def ask(monkeypatch) -> AsyncMock:
    run = AsyncMock()
    monkeypatch.setattr(plain, "run_ask", run)
    monkeypatch.setattr(home, "run_ask", run)
    return run


def _msg(text: str) -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.message_id = next(_ids)
    m.answer = AsyncMock()
    return m


def _cb(data: str) -> MagicMock:
    c = MagicMock(spec=CallbackQuery)
    c.data = data
    c.message = _msg("")
    c.message.edit_text = AsyncMock()
    c.answer = AsyncMock()
    return c


def _sent(m: MagicMock) -> tuple[str, list[str]]:
    call = m.answer.await_args
    kb = call.kwargs.get("reply_markup")
    data = [b.callback_data for row in kb.inline_keyboard for b in row] if kb else []
    return call.args[0], data


def _edited(c: MagicMock) -> str:
    return c.message.edit_text.await_args.args[0]


# --- one-message logging ---------------------------------------------------

async def test_quick_log_message_creates_entries_with_undo(state, user, repo, cipher, container) -> None:
    m = _msg("mood 6 anxiety 7 slept 6.5")
    await plain.plain_text(m, state, user, None, cipher)

    assert [(r.metric_type, float(r.value_numeric)) for r in repo.rows] == [
        ("mood", 6.0), ("anxiety", 7.0), ("sleep_hours", 6.5),
    ]
    text, buttons = _sent(m)
    assert "Mood 6" in text and "Anxiety 7" in text
    ids = ",".join(str(r.id) for r in repo.rows)
    assert f"en:undo:{ids}" in buttons
    assert "en:note" in buttons


async def test_undo_removes_entries(state, user, repo, cipher, container) -> None:
    await plain.plain_text(_msg("mood 6 stress 3"), state, user, None, cipher)
    ids = ",".join(str(r.id) for r in repo.rows)
    c = _cb(f"en:undo:{ids}")
    await entry_actions.on_entry_action(c, state, user, None, cipher)
    assert repo.rows == []
    assert "Undone" in _edited(c)


async def test_undo_refuses_someone_elses_entry(state, user, repo, cipher) -> None:
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    theirs = await EntryService(repo, cipher).create(other, MetricType.MOOD, value_numeric=5)
    c = _cb(f"en:undo:{theirs.id}")
    await entry_actions.on_entry_action(c, state, user, None, cipher)
    assert len(repo.rows) == 1
    assert "Couldn't undo" in c.answer.await_args.args[0]


async def test_add_note_button_starts_note(state, user, repo, cipher) -> None:
    c = _cb("en:note")
    await entry_actions.on_entry_action(c, state, user, None, cipher)
    assert await state.get_state() == JournalFlow.enter_text.state


async def test_thought_button_starts_thought_record(state, user, repo, cipher) -> None:
    c = _cb("en:thought")
    await entry_actions.on_entry_action(c, state, user, None, cipher)
    assert await state.get_state() == ThoughtFlow.situation.state


async def test_quick_scale_confirmation_has_undo(state, user, repo, cipher) -> None:
    await state.set_state(QuickFlow.pick_value)
    await state.update_data(metric="mood")
    c = _cb("quick:3")
    await quick.quick_value_chosen(c, state, user, None, cipher)
    kb = c.message.edit_text.await_args.kwargs["reply_markup"]
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert f"en:undo:{repo.rows[0].id}" in data
    assert "en:thought" in data  # low mood → offer a thought record


# --- plain text router -----------------------------------------------------

async def test_plain_text_offers_choices_and_holds_text(state, user, repo, cipher) -> None:
    m = _msg("rough call with my manager")
    await plain.plain_text(m, state, user, None, cipher)
    text, buttons = _sent(m)
    assert {"pt:note", "pt:thought", "pt:ask", "pt:no"} <= set(buttons)
    assert repo.rows == []
    # The text never goes into button data.
    assert not any("manager" in b for b in buttons)
    assert await state.get_state() == PlainTextFlow.pending.state


async def test_plain_text_save_as_note(state, user, repo, cipher, container) -> None:
    await plain.plain_text(_msg("rough call"), state, user, None, cipher)
    c = _cb("pt:note")
    await plain.on_plain_choice(c, state, user, None, container)
    assert repo.rows[0].metric_type == "note"
    note = await EntryService(repo, cipher).get_for_user(repo.rows[0].id, user)
    assert note.value_text == "rough call"
    assert await state.get_state() is None


async def test_plain_text_to_thought_record_prefills_situation(state, user, repo, cipher, container) -> None:
    await plain.plain_text(_msg("rough call"), state, user, None, cipher)
    await plain.on_plain_choice(_cb("pt:thought"), state, user, None, container)
    assert await state.get_state() == ThoughtFlow.automatic_thought.state
    assert (await state.get_data())["situation_text"] == "rough call"


async def test_plain_text_ask(state, user, repo, cipher, container, ask) -> None:
    await plain.plain_text(_msg("why am I tired on Mondays?"), state, user, None, cipher)
    await plain.on_plain_choice(_cb("pt:ask"), state, user, None, container)
    assert ask.await_args.kwargs["question"] == "why am I tired on Mondays?"
    assert await state.get_state() is None


async def test_plain_text_nothing(state, user, repo, cipher, container) -> None:
    await plain.plain_text(_msg("hmm"), state, user, None, cipher)
    c = _cb("pt:no")
    await plain.on_plain_choice(c, state, user, None, container)
    assert repo.rows == [] and await state.get_state() is None


async def test_plain_choice_after_text_expired(state, user, repo, cipher, container) -> None:
    c = _cb("pt:note")
    await plain.on_plain_choice(c, state, user, None, container)
    assert repo.rows == []
    assert "send it again" in c.answer.await_args.args[0]


async def test_new_text_replaces_pending_one(state, user, repo, cipher, container) -> None:
    await plain.plain_text(_msg("first"), state, user, None, cipher)
    await plain.plain_text(_msg("second"), state, user, None, cipher)
    await plain.on_plain_choice(_cb("pt:note"), state, user, None, container)
    note = await EntryService(repo, cipher).get_for_user(repo.rows[0].id, user)
    assert note.value_text == "second"


# --- home keyboard ---------------------------------------------------------

async def test_home_mood_button_opens_scale(state, user, repo, cipher, container) -> None:
    m = _msg("😊 Mood")
    await home.home_button(m, state, user, None, container)
    assert await state.get_state() == QuickFlow.pick_value.state
    assert (await state.get_data())["metric"] == "mood"


async def test_home_button_works_mid_flow(state, user, repo, cipher, container) -> None:
    await state.set_state(JournalFlow.enter_text)
    await home.home_button(_msg("📝 Note"), state, user, None, container)
    assert await state.get_state() == JournalFlow.enter_text.state
    await home.home_button(_msg("😊 Mood"), state, user, None, container)
    assert await state.get_state() == QuickFlow.pick_value.state


async def test_home_ask_then_question(state, user, repo, cipher, container, ask) -> None:
    await home.home_button(_msg("💬 Ask"), state, user, None, container)
    assert await state.get_state() == AskFlow.question.state
    await home.ask_question_typed(_msg("what helps my sleep?"), state, user, None, container)
    assert ask.await_args.kwargs["question"] == "what helps my sleep?"
    assert await state.get_state() is None


async def test_home_command_shows_adaptive_keyboard(state, user, repo, cipher, container) -> None:
    es = EntryService(repo, cipher)
    for _ in range(3):
        await es.create(user, MetricType.FOCUS, value_numeric=5)
    m = _msg("/home")
    await home.cmd_home(m, MagicMock(args=None), user, None, container)
    kb = m.answer.await_args.kwargs["reply_markup"]
    texts = [b.text for row in kb.keyboard for b in row]
    assert any("Focus" in t for t in texts)


async def test_home_off_removes_keyboard(state, user, repo, cipher, container) -> None:
    from aiogram.types import ReplyKeyboardRemove

    m = _msg("/home off")
    await home.cmd_home(m, MagicMock(args="off"), user, None, container)
    assert isinstance(m.answer.await_args.kwargs["reply_markup"], ReplyKeyboardRemove)
