"""Drive the /migraine handlers end to end: start an attack, then end it.

Handlers are called directly with MagicMock(spec=...) Telegram objects, a
real FSMContext over MemoryStorage, and EntryService over a fake repo — no
Telegram, no Postgres.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot.handlers import migraine as h
from app.bot.states import MigraineFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryService
from tests.unit.fakes import FakeEntryRepo as FakeRepo


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC", language="en")
    u.id = 42
    return u


@pytest.fixture()
def state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )


@pytest.fixture()
def repo(monkeypatch, cipher) -> FakeRepo:
    r = FakeRepo()
    monkeypatch.setattr(h, "entry_service", lambda session, c: EntryService(r, cipher))
    return r


def _msg(text: str) -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.answer = AsyncMock()
    return m


def _cb(data: str) -> MagicMock:
    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _last_text(event: MagicMock) -> str:
    if isinstance(event, CallbackQuery):
        return event.message.edit_text.await_args.args[0]
    return event.answer.await_args.args[0]


def _markup(event: MagicMock):
    if isinstance(event, CallbackQuery):
        return event.message.edit_text.await_args.kwargs.get("reply_markup")
    return event.answer.await_args.kwargs.get("reply_markup")


async def _start_attack(state, user, repo, cipher, *, med: str | None):
    s, c = None, cipher
    await h.cmd_migraine(_msg("/migraine"), state, user, s, c)
    assert await state.get_state() == MigraineFlow.start_time.state

    await h.start_time_tapped(_cb("mg_st:120"), state, user)  # 2h ago
    await h.intensity_tapped(_cb("mg_int:5"), state, user)
    await h.aura_tapped(_cb("mg_aura:1"), state, user)
    await h.symptom_tapped(_cb("mg_sym:nausea"), state, user)
    await h.symptom_tapped(_cb("mg_sym:light"), state, user)
    await h.symptom_tapped(_cb("mg_sym:nausea"), state, user)  # toggled off
    await h.symptom_tapped(_cb("mg_sym:done"), state, user)
    if med:
        await h.medication_typed(_msg(med), state, user)
    else:
        await h.medication_none(_cb("mg_med:none"), state, user)
    done = _msg("bright screen")
    await h.trigger_typed(done, state, user, s, c)
    return done


async def test_full_start_then_end_flow(state, user, repo, cipher) -> None:
    saved = await _start_attack(state, user, repo, cipher, med="ibuprofen 400")

    assert await state.get_state() is None
    assert len(repo.rows) == 1
    row = repo.rows[0]
    assert row.metric_type == MetricType.MIGRAINE.value
    assert "Is it still going?" in _last_text(saved)
    # Encrypted at rest.
    assert row.extra["medication_text"]["__enc__"] is True
    assert row.extra["trigger_text"]["__enc__"] is True
    assert row.extra["symptoms"] == ["light"]
    assert row.extra["aura"] is True

    # "It's over" button → end flow.
    over_cb = _markup(saved).inline_keyboard[0][1].callback_data
    assert over_cb == f"mg_end:{row.id}"
    await h.over_tapped(_cb(over_cb), state, user, None, cipher)
    assert await state.get_state() == MigraineFlow.end_time.state

    await h.end_time_tapped(_cb("mg_et:0"), state, user, None, cipher)
    await h.peak_tapped(_cb("mg_peak:8"), state, user, None, cipher)
    # Medication was recorded at start → goes straight to relief.
    assert await state.get_state() == MigraineFlow.relief.state
    final = _cb("mg_rel:6")
    await h.relief_tapped(final, state, user, None, cipher)

    assert await state.get_state() is None
    es = EntryService(repo, cipher)
    dto = await es.get_for_user(row.id, user)
    assert dto is not None
    assert dto.extra["status"] == "ended"
    assert dto.extra["relief"] == 6
    assert 119 <= dto.extra["duration_minutes"] <= 121
    assert dto.value_numeric == 8.0
    assert "peak 8/10" in _last_text(final)
    assert "2h 0m" in _last_text(final) or "1h 59m" in _last_text(final)


async def test_end_asks_for_medication_when_none_recorded(state, user, repo, cipher) -> None:
    await _start_attack(state, user, repo, cipher, med=None)
    entry_id = repo.rows[0].id

    await h.over_tapped(_cb(f"mg_end:{entry_id}"), state, user, None, cipher)
    await h.end_time_tapped(_cb("mg_et:0"), state, user, None, cipher)
    await h.peak_tapped(_cb("mg_peak:4"), state, user, None, cipher)
    assert await state.get_state() == MigraineFlow.end_medication.state

    await h.end_medication_typed(_msg("paracetamol"), state, user)
    await h.relief_tapped(_cb("mg_rel:3"), state, user, None, cipher)

    dto = await EntryService(repo, cipher).get_for_user(entry_id, user)
    assert dto is not None
    assert dto.extra["medication_text"] == "paracetamol"
    assert dto.extra["relief"] == 3
    # Peak can't be below the onset intensity (5).
    assert dto.value_numeric == 5.0


async def test_migraine_command_offers_to_close_ongoing_attack(state, user, repo, cipher) -> None:
    await _start_attack(state, user, repo, cipher, med=None)
    msg = _msg("/migraine")
    await h.cmd_migraine(msg, state, user, None, cipher)

    assert "Is it over now?" in _last_text(msg)
    buttons = [b.callback_data for b in _markup(msg).inline_keyboard[0]]
    assert buttons == [f"mg_end:{repo.rows[0].id}", "mg_new"]
    assert await state.get_state() is None


async def test_end_time_before_start_reprompts(state, user, repo, cipher) -> None:
    await _start_attack(state, user, repo, cipher, med=None)  # started 2h ago
    entry_id = repo.rows[0].id
    await h.over_tapped(_cb(f"mg_end:{entry_id}"), state, user, None, cipher)

    cb = _cb("mg_et:240")  # "4h ago" — before the start
    await h.end_time_tapped(cb, state, user, None, cipher)

    assert "before it started" in _last_text(cb)
    assert await state.get_state() == MigraineFlow.end_time.state


async def test_typed_garbage_time_reprompts(state, user, repo, cipher) -> None:
    await h.cmd_migraine(_msg("/migraine"), state, user, None, cipher)
    msg = _msg("soonish")
    await h.start_time_typed(msg, state, user)
    assert "type a time like 14:30" in _last_text(msg)
    assert await state.get_state() == MigraineFlow.start_time.state


async def test_over_on_already_ended_attack_fails_gracefully(state, user, repo, cipher) -> None:
    await _start_attack(state, user, repo, cipher, med=None)
    entry_id = repo.rows[0].id
    await h.over_tapped(_cb(f"mg_end:{entry_id}"), state, user, None, cipher)
    await h.end_time_tapped(_cb("mg_et:0"), state, user, None, cipher)
    await h.peak_tapped(_cb("mg_peak:4"), state, user, None, cipher)
    await h.end_medication_none(_cb("mg_emed:none"), state, user, None, cipher)

    stale = _cb(f"mg_end:{entry_id}")  # old button tapped again
    await h.over_tapped(stale, state, user, None, cipher)
    assert "already closed" in _last_text(stale)
    assert await state.get_state() is None
