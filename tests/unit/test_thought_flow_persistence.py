"""Headline test: a /thought flow survives a bot restart mid-conversation.

This is the user story we're solving with PgFsmStorage. The test drives
real `ThoughtFlow` states through `FSMContext` against PgFsmStorage,
discards the storage instance to simulate process death, then continues
the flow on a brand-new storage and confirms (a) the prior reflection
content is still there, decrypted via the same Fernet key, and (b) the
final EntryService.create round-trips through to a normal Entry.
"""
from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select

from app.bot.states import ThoughtFlow
from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.fsm_models import FsmState
from app.infrastructure.fsm_storage import PgFsmStorage


class _FakeEntryRepo:
    """Identical in spirit to the one in test_entry_service.py."""

    def __init__(self) -> None:
        self.rows: list = []
        self._next = 1

    async def add(self, entry):
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(self, *a, **kw):
        return list(self.rows)

    async def daily_aggregates(self, *a, **kw):
        return []


async def test_thought_flow_survives_simulated_restart(fsm_sm, cipher) -> None:
    from app.services.entry_service import EntryService

    key = StorageKey(bot_id=1, chat_id=42, user_id=42)

    # --- Process #1: user types situation + automatic_thought + distortion ---
    storage1 = PgFsmStorage(fsm_sm, cipher)
    ctx1 = FSMContext(storage=storage1, key=key)

    await ctx1.set_state(ThoughtFlow.situation)
    await ctx1.update_data(situation_text="Срыв на встрече")

    await ctx1.set_state(ThoughtFlow.automatic_thought)
    await ctx1.update_data(automatic_thought_text="Я всех подвёл")

    await ctx1.set_state(ThoughtFlow.distortion)
    await ctx1.update_data(distortion_text="all-or-nothing")

    # --- Hard restart: drop process-local state, keep DB. ---
    del storage1, ctx1

    # --- Process #2: brand-new storage instance, same DB, same cipher. ---
    storage2 = PgFsmStorage(fsm_sm, cipher)
    ctx2 = FSMContext(storage=storage2, key=key)

    # State and prior steps' text must come back intact.
    assert await ctx2.get_state() == ThoughtFlow.distortion.state
    data = await ctx2.get_data()
    assert data == {
        "situation_text": "Срыв на встрече",
        "automatic_thought_text": "Я всех подвёл",
        "distortion_text": "all-or-nothing",
    }

    # User finishes the flow on the new process.
    await ctx2.set_state(ThoughtFlow.reframe)
    await ctx2.update_data(reframe_text="Один срыв ≠ полный провал")

    final_data = await ctx2.get_data()
    await ctx2.clear()

    # Mirror what the journal handler does on completion:
    user = User(telegram_id=1, display_name="t", timezone="UTC")
    user.id = 42
    repo = _FakeEntryRepo()
    svc = EntryService(repo, cipher)
    dto = await svc.create(user, MetricType.THOUGHT_RECORD, extra=final_data)

    assert dto.extra == {
        "situation_text": "Срыв на встрече",
        "automatic_thought_text": "Я всех подвёл",
        "distortion_text": "all-or-nothing",
        "reframe_text": "Один срыв ≠ полный провал",
    }

    # And the in-flight FSM row is gone after clear().
    async with fsm_sm() as session:
        rows = (await session.scalars(select(FsmState))).all()
    assert rows == []
