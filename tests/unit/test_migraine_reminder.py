"""Gentle "is it over?" reminders for open migraine attacks.

Rules: first reminder 4h after onset, then every 4h, at most 3, only
08:00-22:00 in the user's tz, never after "Don't remind me". Stamp before
send (a failed send must not cause a reminder every minute).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.domain.models import User
from app.services.entry_service import EntryService
from app.services.migraine_reminder_service import (
    MigraineReminderService,
    reminder_due,
)
from app.services.migraine_service import MigraineService
from tests.unit.fakes import FakeEntryRepo

NOW = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)  # 15:00 UTC — inside waking hours


def _extra(started_h_ago: float, **kw) -> dict:
    return {"status": "ongoing",
            "started_at": (NOW - timedelta(hours=started_h_ago)).isoformat(), **kw}


@pytest.mark.parametrize(
    "extra,due",
    [
        (_extra(3), False),  # too early
        (_extra(4), True),
        (_extra(9, reminder_count=1, reminded_at=(NOW - timedelta(hours=2)).isoformat()), False),
        (_extra(9, reminder_count=1, reminded_at=(NOW - timedelta(hours=4)).isoformat()), True),
        (_extra(20, reminder_count=3, reminded_at=(NOW - timedelta(hours=8)).isoformat()), False),
        (_extra(5, reminders_muted=True), False),
        ({**_extra(5), "status": "ended"}, False),
    ],
)
def test_reminder_due(extra, due) -> None:
    assert reminder_due(extra, NOW) is due


# --- service ------------------------------------------------------------

@pytest.fixture()
def user() -> User:
    u = User(telegram_id=555, display_name="t", timezone="UTC", language="en")
    u.id = 42
    return u


class _Session:
    def __init__(self) -> None:
        self.commit = AsyncMock()


@pytest.fixture()
def repo() -> FakeEntryRepo:
    return FakeEntryRepo()


@pytest.fixture()
def make(repo, cipher):
    def _make(bot):
        session = _Session()

        @asynccontextmanager
        async def sm():
            yield session

        svc = MigraineReminderService(
            sessionmaker=sm,
            migraine_factory=lambda s, now: MigraineService(
                EntryService(repo, cipher), clock=lambda: now
            ),
            bot=bot,
        )
        return svc, session
    return _make


async def _open_attack(repo, cipher, user, hours_ago: float) -> int:
    svc = MigraineService(EntryService(repo, cipher), clock=lambda: NOW)
    a = await svc.start(user, intensity=6, started_at=NOW - timedelta(hours=hours_ago))
    return a.id


async def test_sends_card_with_mute_button_and_stamps(make, repo, cipher, user) -> None:
    entry_id = await _open_attack(repo, cipher, user, 5)
    bot = AsyncMock()
    svc, session = make(bot)

    await svc.maybe_remind(user, now_utc=NOW)

    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 555
    assert "still going" in kwargs["text"]
    data = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert f"mg:over:{entry_id}" in data and f"mg:mute:{entry_id}" in data
    session.commit.assert_awaited()
    assert repo.rows[0].extra["reminder_count"] == 1

    # Next tick right after: not due again.
    await svc.maybe_remind(user, now_utc=NOW + timedelta(minutes=1))
    assert bot.send_message.await_count == 1


async def test_quiet_hours(make, repo, cipher, user) -> None:
    await _open_attack(repo, cipher, user, 5)
    bot = AsyncMock()
    svc, _ = make(bot)
    night = NOW.replace(hour=23)
    await svc.maybe_remind(user, now_utc=night)
    bot.send_message.assert_not_awaited()


async def test_failed_send_is_still_stamped(make, repo, cipher, user) -> None:
    await _open_attack(repo, cipher, user, 5)
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("telegram down")
    svc, _ = make(bot)
    await svc.maybe_remind(user, now_utc=NOW)  # must not raise
    assert repo.rows[0].extra["reminder_count"] == 1


async def test_nothing_open_nothing_sent(make, user) -> None:
    bot = AsyncMock()
    svc, _ = make(bot)
    await svc.maybe_remind(user, now_utc=NOW)
    bot.send_message.assert_not_awaited()


async def test_mute(repo, cipher, user) -> None:
    svc = MigraineService(EntryService(repo, cipher), clock=lambda: NOW)
    a = await svc.start(user, intensity=5, started_at=NOW - timedelta(hours=5))
    dto = await svc.mute_reminders(a.id, user)
    assert dto.extra["reminders_muted"] is True
    assert reminder_due(dto.extra, NOW) is False
