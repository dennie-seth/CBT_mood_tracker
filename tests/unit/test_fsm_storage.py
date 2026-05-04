from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select, update

from app.infrastructure.crypto import FernetCipher
from app.infrastructure.fsm_models import FsmState
from app.infrastructure.fsm_storage import PgFsmStorage


def make_key(
    *,
    bot_id: int = 100,
    chat_id: int = 200,
    user_id: int = 300,
    thread_id: int | None = None,
    business_connection_id: str | None = None,
    destiny: str = "default",
) -> StorageKey:
    return StorageKey(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        business_connection_id=business_connection_id,
        destiny=destiny,
    )


async def test_round_trip_state_and_data_survives_restart(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key()

    secret = "Чувствую тревогу перед встречей"
    await storage.set_state(key, "ThoughtFlow:situation")
    await storage.set_data(key, {"situation_text": secret, "step": 1})

    # 1. Plaintext must NOT live in the DB.
    async with fsm_sm() as session:
        row = await session.scalar(select(FsmState))
    assert row is not None
    assert row.data_encrypted is not None
    assert secret.encode("utf-8") not in row.data_encrypted
    assert b"situation_text" not in row.data_encrypted

    # 2. Simulate a "restart" by constructing a brand-new storage instance
    #    against the same backing store, then read back.
    restarted = PgFsmStorage(fsm_sm, cipher)
    assert await restarted.get_state(key) == "ThoughtFlow:situation"
    assert await restarted.get_data(key) == {"situation_text": secret, "step": 1}


async def test_get_returns_defaults_for_unknown_key(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key(user_id=9999)
    assert await storage.get_state(key) is None
    assert await storage.get_data(key) == {}


async def test_set_data_empty_clears_data_but_preserves_state(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key()
    await storage.set_state(key, "S1")
    await storage.set_data(key, {"x": 1})
    await storage.set_data(key, {})

    # State must still be there; data is cleared.
    assert await storage.get_state(key) == "S1"
    assert await storage.get_data(key) == {}

    async with fsm_sm() as session:
        row = await session.scalar(select(FsmState))
    assert row is not None
    assert row.state == "S1"
    assert row.data_encrypted is None


async def test_clearing_state_and_data_deletes_row(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key()
    await storage.set_state(key, "S1")
    await storage.set_data(key, {"x": 1})

    await storage.set_state(key, None)
    await storage.set_data(key, {})

    async with fsm_sm() as session:
        rows = (await session.scalars(select(FsmState))).all()
    assert rows == []


async def test_update_data_merges(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key()
    await storage.set_data(key, {"a": 1})

    merged = await storage.update_data(key, {"b": 2})
    assert merged == {"a": 1, "b": 2}
    assert await storage.get_data(key) == {"a": 1, "b": 2}


async def test_null_thread_and_business_connection_coalesce(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    # StorageKey accepts None for thread_id / business_connection_id;
    # storage must coalesce these to sentinel values so the PK works.
    key = make_key(thread_id=None, business_connection_id=None)
    await storage.set_state(key, "X")
    await storage.set_data(key, {"k": "v"})

    assert await storage.get_state(key) == "X"
    assert await storage.get_data(key) == {"k": "v"}

    async with fsm_sm() as session:
        row = await session.scalar(select(FsmState))
    assert row is not None
    assert row.thread_id == 0
    assert row.business_connection_id == ""


async def test_keys_are_isolated_per_user(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    a = make_key(user_id=1)
    b = make_key(user_id=2)
    await storage.set_data(a, {"who": "A"})
    await storage.set_data(b, {"who": "B"})
    assert await storage.get_data(a) == {"who": "A"}
    assert await storage.get_data(b) == {"who": "B"}


async def test_opportunistic_cleanup_drops_stale_rows(fsm_sm, cipher) -> None:
    storage = PgFsmStorage(fsm_sm, cipher)
    stale_key = make_key(user_id=1)
    fresh_key = make_key(user_id=2)

    # Seed a row, then back-date its updated_at past the cleanup horizon.
    await storage.set_state(stale_key, "old-state")
    cutoff_target = datetime.now(timezone.utc) - timedelta(
        days=PgFsmStorage.CLEANUP_INTERVAL.days + 1
    )
    async with fsm_sm() as session:
        await session.execute(
            update(FsmState)
            .where(FsmState.user_id == 1)
            .values(updated_at=cutoff_target)
        )
        await session.commit()

    # Any new write must trigger the cleanup as a side effect.
    await storage.set_state(fresh_key, "new-state")

    async with fsm_sm() as session:
        rows = (await session.scalars(select(FsmState))).all()
    assert [r.user_id for r in rows] == [2], "stale row should have been deleted"
