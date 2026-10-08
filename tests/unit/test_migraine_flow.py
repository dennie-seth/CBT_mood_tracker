"""Drive the /migraine handlers end to end with the attack card.

Handlers are called directly with MagicMock(spec=...) Telegram objects, a
real FSMContext over MemoryStorage, and EntryService over the shared fake
repo — no Telegram, no Postgres. The service uses the real clock, so times
are expressed relative to "now".
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from tests.unit.fakes import FakeEntryRepo

_msg_ids = iter(range(1000, 10_000))


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
    monkeypatch.setattr(h, "entry_service", lambda session, c: EntryService(r, cipher))
    return r


@pytest.fixture()
def bot() -> AsyncMock:
    return AsyncMock()


def _msg(text: str) -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.message_id = next(_msg_ids)
    m.answer = AsyncMock()
    return m


def _cb(data: str) -> MagicMock:
    c = MagicMock(spec=CallbackQuery)
    c.data = data
    c.message = MagicMock(spec=Message)
    c.message.chat = MagicMock(id=1)
    c.message.message_id = next(_msg_ids)
    c.message.edit_text = AsyncMock()
    c.answer = AsyncMock()
    return c


def _text(event: MagicMock) -> str:
    if isinstance(event, CallbackQuery):
        return event.message.edit_text.await_args.args[0]
    return event.answer.await_args.args[0]


def _kb_data(kb) -> list[str]:
    return [b.callback_data for row in kb.inline_keyboard for b in row]


def _buttons(event: MagicMock) -> list[str]:
    if isinstance(event, CallbackQuery):
        return _kb_data(event.message.edit_text.await_args.kwargs["reply_markup"])
    return _kb_data(event.answer.await_args.kwargs["reply_markup"])


def _button_texts(event: MagicMock) -> list[str]:
    kb = event.message.edit_text.await_args.kwargs["reply_markup"]
    return [b.text for row in kb.inline_keyboard for b in row]


class Driver:
    """Small helper so tests read like a conversation."""

    def __init__(self, state, user, repo, cipher, bot) -> None:
        self.state, self.user, self.repo, self.cipher, self.bot = state, user, repo, cipher, bot

    async def tap(self, data: str) -> MagicMock:
        c = _cb(data)
        await h.on_card(c, self.state, self.user, None, self.cipher)
        return c

    async def say(self, text: str) -> MagicMock:
        m = _msg(text)
        handler = {
            MigraineFlow.typed_time.state: h.typed_time,
            MigraineFlow.medication.state: h.typed_medication,
            MigraineFlow.trigger_text.state: h.typed_trigger,
        }[await self.state.get_state()]
        await handler(m, self.state, self.user, None, self.cipher, self.bot)
        return m

    async def command(self) -> MagicMock:
        m = _msg("/migraine")
        await h.cmd_migraine(m, self.state, self.user, None, self.cipher)
        return m

    async def attack(self, entry_id: int | None = None):
        e = self.repo.rows[-1] if entry_id is None else next(
            r for r in self.repo.rows if r.id == entry_id
        )
        return await EntryService(self.repo, self.cipher).get_for_user(e.id, self.user)

    async def new_attack(self, intensity: int = 6) -> int:
        await self.tap("mg:newask:0")
        await self.tap(f"mg:new:0:{intensity}")
        return self.repo.rows[-1].id


@pytest.fixture()
def d(state, user, repo, cipher, bot) -> Driver:
    return Driver(state, user, repo, cipher, bot)


# --- starting -----------------------------------------------------------

async def test_one_tap_start_saves_immediately(d) -> None:
    m = await d.command()
    assert "How strong" in _text(m)
    assert "mg:new:0:7" in _buttons(m)

    c = await d.tap("mg:new:0:7")

    a = await d.attack()
    assert a.metric_type == MetricType.MIGRAINE
    assert a.extra["status"] == "ongoing"
    assert a.value_numeric == 7.0
    assert "ongoing" in _text(c)
    assert f"mg:over:{a.id}" in _buttons(c)


async def test_command_lists_every_open_attack_and_offers_new(d) -> None:
    first = await d.new_attack()
    second = await d.new_attack(4)

    m = await d.command()
    calls = m.answer.await_args_list
    assert len(calls) == 2
    first_kb = _kb_data(calls[0].kwargs["reply_markup"])
    last_kb = _kb_data(calls[1].kwargs["reply_markup"])
    assert f"mg:over:{first}" in first_kb
    assert f"mg:over:{second}" in last_kb
    assert "mg:newask:0" in last_kb
    assert "mg:newask:0" not in first_kb


# --- editing details from the card ---------------------------------------

async def test_aura_symptoms_triggers_saved_per_tap(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:aura:{i}")
    await d.tap(f"mg:au:{i}:1")
    await d.tap(f"mg:sym:{i}")
    await d.tap(f"mg:sy:{i}:nausea")
    c = await d.tap(f"mg:sy:{i}:light")
    assert any(t.startswith("✅") for t in _button_texts(c))
    await d.tap(f"mg:trg:{i}")
    await d.tap(f"mg:tg:{i}:sleep")
    await d.tap(f"mg:tg:{i}:stress")
    await d.tap(f"mg:tg:{i}:sleep")  # toggled off

    a = await d.attack(i)
    assert a.extra["aura"] is True
    assert a.extra["symptoms"] == ["nausea", "light"]
    assert a.extra["triggers"] == ["stress"]


async def test_own_trigger_text_typed_and_prompt_retired(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:trg:{i}")
    prompt = await d.tap(f"mg:tgt:{i}")
    assert await d.state.get_state() == MigraineFlow.trigger_text.state

    m = await d.say("long video call")

    a = await d.attack(i)
    assert a.extra["trigger_text"] == "long video call"
    assert d.repo.rows[-1].extra["trigger_text"]["__enc__"] is True
    # The old prompt loses its buttons; a fresh card is sent.
    d.bot.edit_message_text.assert_awaited()
    assert d.bot.edit_message_text.await_args.kwargs["message_id"] == prompt.message.message_id
    assert "long video call" in _text(m)
    assert await d.state.get_state() is None


async def test_medication_typed_then_relief_from_card(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:med:{i}")
    m = await d.say("sumatriptan 50")
    assert f"mg:relief:{i}" in _buttons(m)
    await d.tap(f"mg:relief:{i}")
    await d.tap(f"mg:rl:{i}:7")

    a = await d.attack(i)
    assert a.extra["medication_text"] == "sumatriptan 50"
    assert a.extra["relief"] == 7


async def test_recent_medication_buttons(d) -> None:
    old = await d.new_attack()
    await d.tap(f"mg:med:{old}")
    await d.say("ibuprofen 400")
    await d.tap(f"mg:over:{old}")
    await d.tap(f"mg:end:{old}:0")

    i = await d.new_attack()
    c = await d.tap(f"mg:med:{i}")
    assert "ibuprofen 400" in _button_texts(c)
    await d.tap(f"mg:mp:{i}:0")

    assert (await d.attack(i)).extra["medication_text"] == "ibuprofen 400"


async def test_worse_raises_peak(d) -> None:
    i = await d.new_attack(5)
    await d.tap(f"mg:worse:{i}")
    await d.tap(f"mg:pk:{i}:8")
    assert (await d.attack(i)).value_numeric == 8.0


async def test_start_time_typed_multi_day(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:start:{i}")
    two_days_ago = datetime.now(tz=UTC) - timedelta(days=2)
    await d.say(two_days_ago.strftime("%Y-%m-%d %H:%M"))

    a = await d.attack(i)
    assert a.entry_date == two_days_ago.date()
    assert a.extra["started_at"].startswith(two_days_ago.strftime("%Y-%m-%dT%H:%M"))


async def test_bad_typed_time_keeps_state(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:start:{i}")
    m = await d.say("soonish")
    assert "Couldn't read that" in _text(m)
    assert await d.state.get_state() == MigraineFlow.typed_time.state


# --- closing ------------------------------------------------------------

async def test_close_without_medication(d) -> None:
    i = await d.new_attack(5)
    c = await d.tap(f"mg:over:{i}")
    assert f"mg:end:{i}:0" in _buttons(c)
    c = await d.tap(f"mg:end:{i}:0")
    assert f"mg:pkc:{i}:8" in _buttons(c)
    c = await d.tap(f"mg:pkc:{i}:8")
    assert f"mg:nomed:{i}" in _buttons(c)
    c = await d.tap(f"mg:nomed:{i}")

    a = await d.attack(i)
    assert a.extra["status"] == "ended"
    assert a.value_numeric == 8.0
    assert "Rest well" in _text(c)
    assert await d.state.get_state() is None


async def test_close_with_medication_asks_relief(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:med:{i}")
    await d.say("ibuprofen")
    await d.tap(f"mg:start:{i}")
    await d.tap(f"mg:st:{i}:120")
    await d.tap(f"mg:over:{i}")
    await d.tap(f"mg:end:{i}:60")
    c = await d.tap(f"mg:pkc:{i}:6")
    assert f"mg:rlc:{i}:5" in _buttons(c)
    c = await d.tap(f"mg:rlc:{i}:5")

    a = await d.attack(i)
    assert a.extra["relief"] == 5
    assert "Rest well" in _text(c)


async def test_close_with_typed_end_time_then_medication_typed(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:start:{i}")
    await d.say((datetime.now(tz=UTC) - timedelta(hours=3)).strftime("%H:%M"))
    await d.tap(f"mg:over:{i}")
    await d.say((datetime.now(tz=UTC) - timedelta(hours=1)).strftime("%H:%M"))
    await d.tap(f"mg:pkc:{i}:7")
    m = await d.say("paracetamol")
    assert f"mg:rlc:{i}:3" in _buttons(m)
    await d.tap(f"mg:rlc:{i}:3")

    a = await d.attack(i)
    assert a.extra["status"] == "ended"
    assert 119 <= a.extra["duration_minutes"] <= 121
    assert a.extra["medication_text"] == "paracetamol"


async def test_typed_end_before_start_is_rejected_kindly(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:over:{i}")
    m = await d.say((datetime.now(tz=UTC) - timedelta(hours=2)).strftime("%H:%M"))
    assert "can't be before the start" in _text(m)
    assert await d.state.get_state() == MigraineFlow.typed_time.state
    assert (await d.attack(i)).extra["status"] == "ongoing"


async def test_forgot_end(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:forgot:{i}")
    a = await d.attack(i)
    assert a.extra["status"] == "ended"
    assert a.extra["end_unknown"] is True


async def test_edit_end_time_after_closing(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:start:{i}")
    await d.tap(f"mg:st:{i}:240")  # started 4h ago
    await d.tap(f"mg:over:{i}")
    await d.tap(f"mg:end:{i}:0")
    await d.tap(f"mg:nomed:{i}")
    await d.tap(f"mg:endtime:{i}")
    await d.tap(f"mg:et:{i}:120")
    assert 119 <= (await d.attack(i)).extra["duration_minutes"] <= 121


# --- delete / safety ----------------------------------------------------

async def test_delete_needs_confirmation(d) -> None:
    i = await d.new_attack()
    c = await d.tap(f"mg:del:{i}")
    assert "can't be undone" in _text(c)
    assert len(d.repo.rows) == 1
    c = await d.tap(f"mg:dely:{i}")
    assert d.repo.rows == []
    assert _text(c) == "Deleted."


async def test_other_users_attack_is_refused(d, cipher) -> None:
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    theirs = await EntryService(d.repo, cipher).create(
        other, MetricType.MIGRAINE, value_numeric=5,
        extra={"status": "ongoing", "started_at": datetime.now(tz=UTC).isoformat(),
               "start_intensity": 5, "peak_intensity": 5},
    )
    c = await d.tap(f"mg:dely:{theirs.id}")
    assert len(d.repo.rows) == 1
    assert "can't find" in c.answer.await_args.args[0]
    assert c.answer.await_args.kwargs.get("show_alert") is True


async def test_buttons_from_old_version_get_a_gentle_answer(d) -> None:
    c = _cb("mg_end:5")
    await h.stale_button(c, d.user)
    assert "earlier step" in c.answer.await_args.args[0]


async def test_card_action_clears_pending_text_step(d) -> None:
    i = await d.new_attack()
    await d.tap(f"mg:med:{i}")  # waiting for a typed medication
    await d.tap(f"mg:aura:{i}")  # user moved on
    assert await d.state.get_state() is None


async def test_mute_button_from_reminder(d) -> None:
    i = await d.new_attack()
    c = await d.tap(f"mg:mute:{i}")
    assert (await d.attack(i)).extra["reminders_muted"] is True
    assert "ongoing" in _text(c)



async def test_migraines_summary_command(d) -> None:
    i = await d.new_attack(7)
    await d.tap(f"mg:sym:{i}")
    await d.tap(f"mg:sy:{i}:nausea")
    await d.tap(f"mg:med:{i}")
    await d.say("ibuprofen 400")
    await d.tap(f"mg:start:{i}")
    await d.tap(f"mg:st:{i}:240")
    await d.tap(f"mg:over:{i}")
    await d.tap(f"mg:end:{i}:0")
    await d.tap(f"mg:rlc:{i}:6")

    m = _msg("/migraines")
    command = MagicMock(args=None)
    await h.cmd_migraines(m, command, d.user, None, d.cipher)
    out = _text(m)
    assert "Attacks: 1" in out
    assert "Nausea" in out
    assert "ibuprofen 400" in out and "6" in out


async def test_migraines_summary_empty(d) -> None:
    m = _msg("/migraines")
    await h.cmd_migraines(m, MagicMock(args="7d"), d.user, None, d.cipher)
    assert "No migraine attacks" in _text(m)


async def test_migraines_summary_bad_period(d) -> None:
    m = _msg("/migraines")
    await h.cmd_migraines(m, MagicMock(args="lots"), d.user, None, d.cipher)
    assert "7d" in _text(m)
