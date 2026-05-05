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


async def test_clear_after_state_only_flow_does_not_crash(fsm_sm, cipher) -> None:
    """Regression: aiogram's ``FSMContext.clear()`` calls ``set_state(None)``
    then ``set_data({})``. The first call deletes the row (state was the
    only thing on it), so the second call finds nothing, used to add a
    fresh empty row, and then immediately tried to ``session.delete()`` it
    while still pending — raising ``InvalidRequestError`` and rolling back
    the surrounding handler's DB writes (e.g. an entry that just got
    created via ``/note``).

    This used to corrupt the /note two-step flow: the entry was inserted
    in the same transaction, but state.clear() raised, so the middleware
    rolled the entry back too. Repro: set state only (no data), then
    clear() — must not raise, and the row must be gone.
    """
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key()
    await storage.set_state(key, "JournalFlow:enter_text")

    # Mirror aiogram's FSMContext.clear() exactly.
    await storage.set_state(key, None)
    await storage.set_data(key, {})  # this is what used to raise

    async with fsm_sm() as session:
        rows = (await session.scalars(select(FsmState))).all()
    assert rows == []


async def test_set_data_empty_when_no_row_exists_is_noop(fsm_sm, cipher) -> None:
    """A bare ``set_data({})`` against a key that has never been touched
    must not create a phantom empty row — and must not crash."""
    storage = PgFsmStorage(fsm_sm, cipher)
    key = make_key(user_id=42)
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


async def test_get_data_survives_key_rotation_with_unreadable_blob(fsm_sm, cipher) -> None:
    """After Fernet key rotation removes the key that encrypted an in-flight
    FSM blob, a stale row must NOT crash the next handler — return {} and
    self-heal by deleting the unreadable row.
    """
    from cryptography.fernet import Fernet
    from app.infrastructure.crypto import FernetCipher
    from app.infrastructure.fsm_storage import PgFsmStorage

    # Storage A encrypts with KEY_OLD.
    old_key = Fernet.generate_key().decode()
    storage_old = PgFsmStorage(fsm_sm, FernetCipher([old_key]))
    key = make_key()
    await storage_old.set_state(key, "MidFlow:step1")
    await storage_old.set_data(key, {"sensitive": "Чувствую тревогу"})

    # Storage B has only KEY_NEW — operator removed KEY_OLD before re-encryption.
    new_key = Fernet.generate_key().decode()
    storage_new = PgFsmStorage(fsm_sm, FernetCipher([new_key]))

    # Must not raise. Returns {} (unreadable → effectively absent).
    assert await storage_new.get_data(key) == {}

    # Self-heal: the stale row should be gone so subsequent flows start fresh.
    rows = []
    async with fsm_sm() as session:
        rows = (await session.scalars(select(FsmState))).all()
    assert rows == []


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
