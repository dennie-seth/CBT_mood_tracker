"""EntryService.update_extra is the single mutation chokepoint for plan
status updates etc. It must:

- refuse to mutate an entry owned by a different user (AuthZ chokepoint
  mirrors the rest of the codebase: handlers always pass the
  authenticated user).
- re-encrypt `*_text` keys in the new extra before persisting.
- enforce the same MAX_TEXT_BYTES cap as `create`.
- return the fresh DTO with decrypted values.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from app.domain.enums import MetricType
from app.domain.models import Entry, User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import MAX_TEXT_BYTES, EntryService


class FakeRepo:
    """Adds a `get_for_user` and a flush() for update tests."""

    def __init__(self) -> None:
        self.rows: list[Entry] = []
        self._next = 1

    async def add(self, entry: Entry) -> Entry:
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(self, *a, **kw):
        return list(self.rows)

    async def daily_aggregates(self, *a, **kw):
        return []

    async def get_for_user(self, entry_id: int, user_id: int) -> Entry | None:
        for r in self.rows:
            if r.id == entry_id and r.user_id == user_id:
                return r
        return None

    async def exists(self, entry_id: int) -> bool:
        return any(r.id == entry_id for r in self.rows)


@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC")
    u.id = 42
    return u


async def test_update_extra_round_trips_encryption(cipher, user) -> None:
    repo = FakeRepo()
    svc = EntryService(repo, cipher)
    plan = await svc.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={"plan_text": "walk in the park", "predicted_effect": 7, "status": "scheduled"},
    )

    new_extra = {
        "plan_text": "walk in the park",  # unchanged
        "predicted_effect": 7,
        "status": "done",
        "completed_at": "2026-05-08T19:30:00+00:00",
        "actual_effect": 8,
    }
    updated = await svc.update_extra(plan.id, user, new_extra)

    assert updated.extra is not None
    assert updated.extra["status"] == "done"
    assert updated.extra["actual_effect"] == 8
    assert updated.extra["plan_text"] == "walk in the park"  # decrypted

    # In storage, plan_text still encrypted.
    raw = repo.rows[0].extra
    assert isinstance(raw["plan_text"], dict) and raw["plan_text"].get("__enc__") is True


async def test_update_extra_refuses_other_user(cipher, user) -> None:
    repo = FakeRepo()
    svc = EntryService(repo, cipher)
    plan = await svc.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={"plan_text": "secret", "status": "scheduled"},
    )

    other = User(telegram_id=999, display_name="other", timezone="UTC")
    other.id = 99
    with pytest.raises(PermissionError):
        await svc.update_extra(plan.id, other, {"status": "done"})


async def test_update_extra_unknown_id_raises(cipher, user) -> None:
    svc = EntryService(FakeRepo(), cipher)
    with pytest.raises(LookupError):
        await svc.update_extra(9999, user, {"status": "done"})


async def test_update_extra_enforces_text_size_cap(cipher, user) -> None:
    repo = FakeRepo()
    svc = EntryService(repo, cipher)
    plan = await svc.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={"plan_text": "ok", "status": "scheduled"},
    )

    huge = "x" * (MAX_TEXT_BYTES + 1)
    with pytest.raises(ValueError):
        await svc.update_extra(plan.id, user, {"plan_text": "ok", "skip_reason_text": huge})
