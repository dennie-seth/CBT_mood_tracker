"""Hard moments: "things that helped you before" + /breathe.

Support shows the user's OWN words (coping entries, activities that
helped them most) — no AI, no advice — and offers a breathing / grounding
exercise that needs no typing.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot import support
from app.bot.handlers import breathe, quick
from app.bot.states import QuickFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryService
from app.services.support_service import SupportService
from tests.unit.fakes import FakeEntryRepo

TODAY = date(2026, 10, 8)
_ids = iter(range(1000, 100_000))


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC", language="en")
    u.id = 42
    return u


@pytest.fixture()
def repo() -> FakeEntryRepo:
    return FakeEntryRepo()


@pytest.fixture()
def es(repo, cipher) -> EntryService:
    return EntryService(repo, cipher)


@pytest.fixture(autouse=True)
def _reset_cooldown():
    support.reset_cooldowns()


def _at(days_ago: int) -> datetime:
    d = TODAY - timedelta(days=days_ago)
    return datetime(d.year, d.month, d.day, 12, tzinfo=UTC)


async def _plan(es, user, days_ago: int, text: str, actual: int) -> None:
    await es.create(
        user, MetricType.ACTIVITY_PLAN, recorded_at=_at(days_ago),
        extra={"plan_text": text, "status": "done", "predicted_effect": 4, "actual_effect": actual},
    )


# --- SupportService ----------------------------------------------------------

async def test_helped_before_uses_own_words(es, user) -> None:
    await es.create(user, MetricType.COPING, value_text="cold water on my face", recorded_at=_at(20))
    await es.create(user, MetricType.COPING, value_text="Call Anna", recorded_at=_at(3))
    await es.create(user, MetricType.COPING, value_text="call anna", recorded_at=_at(2))
    await _plan(es, user, 10, "walk by the river", 9)
    await _plan(es, user, 9, "tidy desk", 5)  # didn't help much → not shown
    await _plan(es, user, 8, "Walk by the river", 8)

    got = await SupportService(es).helped_before(user.id, today=TODAY)
    assert got == ["call anna", "cold water on my face", "walk by the river"]


async def test_helped_before_empty(es, user) -> None:
    assert await SupportService(es).helped_before(user.id, today=TODAY) == []


# --- offer_support -----------------------------------------------------------

def _msg(text: str = "") -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = text
    m.chat = MagicMock(id=1)
    m.message_id = next(_ids)
    m.answer = AsyncMock()
    m.edit_text = AsyncMock()
    return m


def _kb(call) -> list[str]:
    kb = call.kwargs.get("reply_markup")
    return [b.callback_data for row in kb.inline_keyboard for b in row] if kb else []


@pytest.mark.parametrize(
    "readings,offered",
    [
        ([(MetricType.ANXIETY, 8.0)], True),
        ([(MetricType.STRESS, 9.0)], True),
        ([(MetricType.MOOD, 3.0)], True),
        ([(MetricType.ANXIETY, 7.0)], False),
        ([(MetricType.MOOD, 4.0), (MetricType.ENERGY, 2.0)], False),
    ],
)
async def test_offer_only_for_hard_readings(es, user, readings, offered) -> None:
    m = _msg()
    await support.offer_support(m, user, es, readings)
    assert m.answer.await_count == (1 if offered else 0)


async def test_offer_lists_own_words_and_exercises(es, user) -> None:
    await es.create(user, MetricType.COPING, value_text="cold water on my face")
    m = _msg()
    await support.offer_support(m, user, es, [(MetricType.ANXIETY, 9.0)])
    text = m.answer.await_args.args[0]
    assert "helped you before" in text and "cold water on my face" in text
    assert {"br:box", "br:ground"} <= set(_kb(m.answer.await_args))


async def test_offer_without_history_still_offers_exercises(es, user) -> None:
    m = _msg()
    await support.offer_support(m, user, es, [(MetricType.ANXIETY, 9.0)])
    assert "helped you before" not in m.answer.await_args.args[0]
    assert "br:box" in _kb(m.answer.await_args)


async def test_offer_has_cooldown(es, user) -> None:
    m1, m2 = _msg(), _msg()
    await support.offer_support(m1, user, es, [(MetricType.ANXIETY, 9.0)])
    await support.offer_support(m2, user, es, [(MetricType.ANXIETY, 9.0)])
    assert m1.answer.await_count == 1 and m2.answer.await_count == 0


async def test_quick_log_hard_reading_triggers_offer(es, repo, user, cipher, monkeypatch) -> None:
    monkeypatch.setattr(quick, "entry_service", lambda s, c: EntryService(repo, cipher))
    offer = AsyncMock()
    monkeypatch.setattr(quick, "offer_support", offer)
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.set_state(QuickFlow.pick_value)
    await state.update_data(metric="anxiety")
    c = MagicMock(spec=CallbackQuery)
    c.data = "quick:9"
    c.message = _msg()
    c.answer = AsyncMock()
    await quick.quick_value_chosen(c, state, user, None, cipher)
    assert offer.await_args.args[3] == [(MetricType.ANXIETY, 9.0)]


# --- /breathe ----------------------------------------------------------------

async def test_breathe_offers_both_exercises(user) -> None:
    m = _msg("/breathe")
    await breathe.cmd_breathe(m, user)
    assert {"br:box", "br:ground"} <= set(_kb(m.answer.await_args))


async def test_box_breathing_runs_all_phases(user) -> None:
    msg = _msg()
    sleep = AsyncMock()
    await breathe.run_box_breathing(msg, user.language, rounds=2, sleep=sleep)
    texts = [c.args[0] for c in msg.edit_text.await_args_list]
    assert len(texts) == 2 * 4 + 1
    assert "Breathe in" in texts[0] and "round 1/2" in texts[0]
    assert "round 2/2" in texts[4]
    assert "Well done" in texts[-1]
    assert "br:log" in _kb(msg.edit_text.await_args_list[-1])
    assert sleep.await_count == 2 * 4


async def test_box_breathing_can_be_stopped(user) -> None:
    msg = _msg()

    async def sleep(_):
        breathe.request_stop(msg.chat.id, msg.message_id)

    await breathe.run_box_breathing(msg, user.language, rounds=4, sleep=sleep)
    texts = [c.args[0] for c in msg.edit_text.await_args_list]
    assert len(texts) == 2
    assert "Stopped" in texts[-1]


async def test_grounding_steps(user) -> None:
    c = MagicMock(spec=CallbackQuery)
    c.message = _msg()
    c.answer = AsyncMock()
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    texts = []
    for data in ("br:ground", "gr:4", "gr:3", "gr:2", "gr:1", "gr:0"):
        c.data = data
        await breathe.on_breathe(c, state, user)
        texts.append(c.message.edit_text.await_args.args[0])
    assert "5 things you can see" in texts[0]
    assert "1 thing you can taste" in texts[4]
    assert "here, now" in texts[5]


async def test_log_anxiety_after_breathing(user) -> None:
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    c = MagicMock(spec=CallbackQuery)
    c.data = "br:log"
    c.message = _msg()
    c.answer = AsyncMock()
    await breathe.on_breathe(c, state, user)
    assert await state.get_state() == QuickFlow.pick_value.state
    assert (await state.get_data())["metric"] == "anxiety"
