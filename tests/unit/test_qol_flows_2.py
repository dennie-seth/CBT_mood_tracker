"""/day card, /recent and the distortion buttons in /thought."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import day, journal, recent
from app.bot.states import RecentFlow, ThoughtFlow
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
    for mod in (day, recent, journal):
        monkeypatch.setattr(mod, "entry_service", make)
    return r


@pytest.fixture()
def es(repo, cipher) -> EntryService:
    return EntryService(repo, cipher)


def _msg(text: str = "") -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.message_id = next(_ids)
    m.answer = AsyncMock()
    m.edit_text = AsyncMock()
    return m


def _cb(data: str) -> MagicMock:
    c = MagicMock(spec=CallbackQuery)
    c.data = data
    c.message = _msg()
    c.answer = AsyncMock()
    return c


def _kb(call) -> list[str]:
    kb = call.kwargs.get("reply_markup")
    return [b.callback_data for row in kb.inline_keyboard for b in row] if kb else []


def _labels(call) -> list[str]:
    kb = call.kwargs.get("reply_markup")
    return [b.text for row in kb.inline_keyboard for b in row] if kb else []


# --- /day ------------------------------------------------------------------

async def _tap(state, user, cipher, data: str) -> MagicMock:
    c = _cb(data)
    await day.on_day(c, state, user, None, cipher)
    return c


async def test_day_card_steps_through_and_saves_each(state, user, repo, cipher) -> None:
    m = _msg("/day")
    await day.cmd_day(m, state, user)
    assert "mood" in m.answer.await_args.args[0].lower()
    assert {"dc:mood:6", "dc:mood:skip"} <= set(_kb(m.answer.await_args))

    c = await _tap(state, user, cipher, "dc:mood:6")
    assert len(repo.rows) == 1  # saved immediately
    assert "energy" in c.message.edit_text.await_args.args[0].lower()
    await _tap(state, user, cipher, "dc:energy:skip")
    await _tap(state, user, cipher, "dc:anxiety:7")
    c = await _tap(state, user, cipher, "dc:sleep_quality:5")

    assert [(r.metric_type, float(r.value_numeric)) for r in repo.rows] == [
        ("mood", 6.0), ("anxiety", 7.0), ("sleep_quality", 5.0),
    ]
    final = c.message.edit_text.await_args
    assert "Mood 6" in final.args[0] and "Anxiety 7" in final.args[0]
    assert "Energy" not in final.args[0]
    ids = ",".join(str(r.id) for r in repo.rows)
    assert f"en:undo:{ids}" in _kb(final)
    assert await state.get_state() is None


async def test_day_card_ignores_out_of_order_or_stale_taps(state, user, repo, cipher) -> None:
    c = await _tap(state, user, cipher, "dc:mood:6")  # no /day running
    assert repo.rows == []
    c.answer.assert_awaited()

    await day.cmd_day(_msg("/day"), state, user)
    c = await _tap(state, user, cipher, "dc:anxiety:7")  # not the current step
    assert repo.rows == []


# --- /recent ---------------------------------------------------------------

async def test_recent_lists_newest_first(state, user, repo, es) -> None:
    a = await es.create(user, MetricType.MOOD, value_numeric=4)
    b = await es.create(user, MetricType.NOTE, value_text="evening walk")
    m = _msg("/recent")
    await recent.cmd_recent(m, state, user, None, es._cipher)
    data = _kb(m.answer.await_args)
    assert data[:2] == [f"rc:open:{b.id}", f"rc:open:{a.id}"]
    # Note text is shown to the user in the label, never put into callback data.
    assert any("evening walk" in label for label in _labels(m.answer.await_args))


async def test_recent_edit_numeric(state, user, repo, es, cipher) -> None:
    a = await es.create(user, MetricType.MOOD, value_numeric=4)
    c = _cb(f"rc:open:{a.id}")
    await recent.on_recent(c, state, user, None, cipher)
    assert f"rc:val:{a.id}" in _kb(c.message.edit_text.await_args)
    await recent.on_recent(_cb(f"rc:val:{a.id}"), state, user, None, cipher)
    await recent.on_recent(_cb(f"rc:set:{a.id}:7"), state, user, None, cipher)
    assert float(repo.rows[0].value_numeric) == 7.0


async def test_recent_edit_text(state, user, repo, es, cipher) -> None:
    n = await es.create(user, MetricType.NOTE, value_text="tpyo")
    await recent.on_recent(_cb(f"rc:txt:{n.id}"), state, user, None, cipher)
    assert await state.get_state() == RecentFlow.edit_text.state
    m = _msg("typo")
    await recent.recent_text_typed(m, state, user, None, cipher)
    assert (await es.get_for_user(n.id, user)).value_text == "typo"
    assert await state.get_state() is None


async def test_recent_delete_with_confirmation(state, user, repo, es, cipher) -> None:
    a = await es.create(user, MetricType.MOOD, value_numeric=4)
    c = _cb(f"rc:del:{a.id}")
    await recent.on_recent(c, state, user, None, cipher)
    assert len(repo.rows) == 1
    await recent.on_recent(_cb(f"rc:dely:{a.id}"), state, user, None, cipher)
    assert repo.rows == []


async def test_recent_thought_record_is_delete_only(state, user, repo, es, cipher) -> None:
    tr = await es.create(user, MetricType.THOUGHT_RECORD, extra={"situation_text": "s"})
    c = _cb(f"rc:open:{tr.id}")
    await recent.on_recent(c, state, user, None, cipher)
    data = _kb(c.message.edit_text.await_args)
    assert f"rc:del:{tr.id}" in data
    assert f"rc:val:{tr.id}" not in data and f"rc:txt:{tr.id}" not in data


async def test_recent_migraine_opens_attack_card(state, user, repo, es, cipher) -> None:
    from app.services.migraine_service import MigraineService

    a = await MigraineService(es).start(user, intensity=5)
    c = _cb(f"rc:open:{a.id}")
    await recent.on_recent(c, state, user, None, cipher)
    assert f"mg:card:{a.id}" in _kb(c.message.edit_text.await_args)


async def test_recent_refuses_someone_elses_entry(state, user, repo, es, cipher) -> None:
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    theirs = await es.create(other, MetricType.NOTE, value_text="private")
    c = _cb(f"rc:open:{theirs.id}")
    await recent.on_recent(c, state, user, None, cipher)
    c.message.edit_text.assert_not_awaited()
    assert c.answer.await_args.kwargs.get("show_alert") is True
    await recent.on_recent(_cb(f"rc:dely:{theirs.id}"), state, user, None, cipher)
    assert len(repo.rows) == 1


# --- distortion buttons -----------------------------------------------------

async def test_distortion_prompt_has_buttons(state, user) -> None:
    await state.set_state(ThoughtFlow.automatic_thought)
    m = _msg("I'll fail")
    await journal.thought_auto(m, state, user)
    data = _kb(m.answer.await_args)
    assert "td:mind_reading" in data and "td:catastrophising" in data and "td:other" in data


async def test_distortion_button_saves_label_and_moves_on(state, user) -> None:
    await state.set_state(ThoughtFlow.distortion)
    c = _cb("td:mind_reading")
    await journal.distortion_tapped(c, state, user)
    assert await state.get_state() == ThoughtFlow.reframe.state
    assert (await state.get_data())["distortion_text"] == "Mind reading"


async def test_distortion_other_lets_user_type(state, user) -> None:
    await state.set_state(ThoughtFlow.distortion)
    c = _cb("td:other")
    await journal.distortion_tapped(c, state, user)
    assert await state.get_state() == ThoughtFlow.distortion.state
    m = _msg("magnification")
    await journal.thought_distortion(m, state, user)
    assert (await state.get_data())["distortion_text"] == "magnification"
