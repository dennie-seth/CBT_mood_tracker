"""ActivationService: tiny façade over EntryService for BA plans."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from cryptography.fernet import Fernet

from app.domain.enums import MetricType
from app.domain.models import Entry, User
from app.infrastructure.crypto import FernetCipher
from app.services.activation_service import ActivationService
from app.services.entry_service import EntryService


class FakeRepo:
    def __init__(self) -> None:
        self.rows: list[Entry] = []
        self._next = 1

    async def add(self, entry: Entry) -> Entry:
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(self, user_id, start, end, metric_types=None):
        out = [
            r for r in self.rows
            if r.user_id == user_id and start <= r.entry_date <= end
        ]
        if metric_types:
            out = [r for r in out if r.metric_type in metric_types]
        return out

    async def daily_aggregates(self, *a, **kw):
        return []

    async def get_for_user(self, entry_id, user_id):
        for r in self.rows:
            if r.id == entry_id and r.user_id == user_id:
                return r
        return None

    async def exists(self, entry_id):
        return any(r.id == entry_id for r in self.rows)


@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC")
    u.id = 42
    return u


def _plan_dto_for(svc, user, when, plan_text, predicted, status="scheduled"):
    """Helper to set up a plan via EntryService.create."""
    return svc.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={
            "plan_text": plan_text,
            "planned_for": when.isoformat(),
            "predicted_effect": predicted,
            "status": status,
        },
        recorded_at=datetime(when.year, when.month, when.day, 12, 0, tzinfo=timezone.utc),
    )


# --- list_open_plans ---

async def test_list_open_plans_filters_by_status(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    await _plan_dto_for(es, user, date(2026, 5, 5), "walk", 7)  # scheduled
    p2 = await _plan_dto_for(es, user, date(2026, 5, 6), "call", 5)
    # Mark p2 done by direct service.update_extra
    await es.update_extra(p2.id, user, {
        "plan_text": "call",
        "planned_for": "2026-05-06",
        "predicted_effect": 5,
        "status": "done",
        "actual_effect": 6,
    })

    svc = ActivationService(es)
    plans = await svc.list_open_plans(user.id, on_or_before=date(2026, 5, 31))
    assert len(plans) == 1
    assert plans[0].extra["plan_text"] == "walk"


async def test_list_open_plans_filters_by_date_window(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    await _plan_dto_for(es, user, date(2026, 5, 5), "early", 5)
    await _plan_dto_for(es, user, date(2026, 5, 20), "late", 5)

    svc = ActivationService(es)
    today = date(2026, 5, 10)
    plans = await svc.list_open_plans(user.id, on_or_before=today)
    texts = [p.extra["plan_text"] for p in plans]
    assert texts == ["early"]


# --- mark_done ---

async def test_mark_done_sets_status_and_actual_effect(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    p = await _plan_dto_for(es, user, date(2026, 5, 5), "walk", 7)

    svc = ActivationService(es)
    updated = await svc.mark_done(p.id, user, actual_effect=8)

    assert updated.extra["status"] == "done"
    assert updated.extra["actual_effect"] == 8
    assert updated.extra["plan_text"] == "walk"  # preserved (re-encrypted)
    assert updated.extra["predicted_effect"] == 7  # preserved
    assert "completed_at" in updated.extra


async def test_mark_done_refuses_already_done_plan(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    p = await _plan_dto_for(es, user, date(2026, 5, 5), "walk", 7)
    svc = ActivationService(es)
    await svc.mark_done(p.id, user, actual_effect=8)

    with pytest.raises(ValueError, match="already"):
        await svc.mark_done(p.id, user, actual_effect=9)


async def test_mark_done_only_works_on_activity_plan(cipher, user) -> None:
    """If the entry id points at a NOTE, ActivationService should refuse."""
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    note = await es.create(user, MetricType.NOTE, value_text="not a plan")

    svc = ActivationService(es)
    with pytest.raises(ValueError, match="not a behavioral activation plan"):
        await svc.mark_done(note.id, user, actual_effect=5)


# --- mark_skipped ---

async def test_mark_skipped_with_reason(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    p = await _plan_dto_for(es, user, date(2026, 5, 5), "walk", 7)

    svc = ActivationService(es)
    updated = await svc.mark_skipped(p.id, user, reason_text="weather")

    assert updated.extra["status"] == "skipped"
    assert updated.extra["skip_reason_text"] == "weather"  # decrypted

    # On the wire, skip_reason_text is encrypted.
    raw = repo.rows[0].extra
    assert isinstance(raw["skip_reason_text"], dict)
    assert raw["skip_reason_text"].get("__enc__") is True


async def test_mark_skipped_without_reason(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    p = await _plan_dto_for(es, user, date(2026, 5, 5), "walk", 7)

    svc = ActivationService(es)
    updated = await svc.mark_skipped(p.id, user, reason_text=None)
    assert updated.extra["status"] == "skipped"
    assert "skip_reason_text" not in updated.extra
