"""Headline test for the once-per-minute scheduler tick.

Two users are configured: one due, one not. After one tick, only the
due user gets a summary, and only their last-sent date is stamped.
"""
from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock

import pytz

from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.schedule_service import SummaryScheduler


async def _seed_user(sm, *, id: int, telegram_id: int, tz: str) -> User:
    async with sm() as session:
        u = User(id=id, telegram_id=telegram_id, display_name=f"u{id}", timezone=tz)
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


async def test_tick_dispatches_only_due_users(schedule_sm) -> None:
    # Two users: one in Berlin with daily 21:00 (due at 21:00 local),
    # one in Los_Angeles with daily 21:00 (NOT due at 21:00 Berlin = 12:00 LA).
    berlin_user = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="Europe/Berlin")
    la_user = await _seed_user(schedule_sm, id=2, telegram_id=222, tz="America/Los_Angeles")

    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(berlin_user.id, enabled=True, at=time(21, 0))
        await repo.set_daily(la_user.id, enabled=True, at=time(21, 0))
        await session.commit()

    delivery = AsyncMock()
    scheduler = SummaryScheduler(sessionmaker=schedule_sm, delivery=delivery)

    # 19:00 UTC == 21:00 Berlin (DST) == 12:00 Los_Angeles.
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 19, 0))
    await scheduler.dispatch_due(now_utc)

    # Only Berlin user's daily should be dispatched.
    assert delivery.await_count == 1
    args, kwargs = delivery.call_args
    user_arg = kwargs.get("user", args[0] if args else None)
    kind_arg = kwargs.get("kind", args[1] if len(args) > 1 else None)
    assert user_arg.telegram_id == 111
    assert kind_arg == "daily"


async def test_tick_no_double_send_after_stamp(schedule_sm) -> None:
    """Second tick within the same local-day should NOT re-deliver."""
    user = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="Europe/Berlin")
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0))
        await session.commit()

    delivered: list = []

    async def fake_delivery(*, user, kind, local_today) -> None:
        delivered.append((user.telegram_id, kind, local_today))
        # Mimic real SummaryService: stamp last_sent_date so the next tick is idempotent.
        async with schedule_sm() as session:
            await SqlScheduleRepository(session).stamp_daily_sent(user.id, on=local_today)
            await session.commit()

    scheduler = SummaryScheduler(sessionmaker=schedule_sm, delivery=fake_delivery)
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 19, 0))

    await scheduler.dispatch_due(now_utc)
    await scheduler.dispatch_due(now_utc)  # same minute, should be a no-op
    await scheduler.dispatch_due(pytz.utc.localize(datetime(2026, 5, 4, 22, 0)))  # later same day

    assert len(delivered) == 1


async def test_tick_swallows_per_user_failures(schedule_sm) -> None:
    """A failing delivery for one user must not block delivery to another."""
    u1 = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="Europe/Berlin")
    u2 = await _seed_user(schedule_sm, id=2, telegram_id=222, tz="Europe/Berlin")
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(u1.id, enabled=True, at=time(21, 0))
        await repo.set_daily(u2.id, enabled=True, at=time(21, 0))
        await session.commit()

    delivered = []

    async def flaky_delivery(*, user, kind, local_today) -> None:
        if user.telegram_id == 111:
            raise RuntimeError("boom")
        delivered.append(user.telegram_id)

    scheduler = SummaryScheduler(sessionmaker=schedule_sm, delivery=flaky_delivery)
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 19, 0))
    await scheduler.dispatch_due(now_utc)

    # u2 still got delivered despite u1 raising.
    assert delivered == [222]


async def test_tick_skips_users_no_longer_in_allowlist(schedule_sm) -> None:
    """If the operator removes a Telegram ID from ALLOWED_TELEGRAM_IDS to revoke
    access, the scheduler must NOT keep delivering Haiku summaries (which contain
    decrypted excerpts of past entries) to that user. The allowlist is the gate
    even for proactive output."""
    revoked = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="Europe/Berlin")
    active = await _seed_user(schedule_sm, id=2, telegram_id=222, tz="Europe/Berlin")
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(revoked.id, enabled=True, at=time(21, 0))
        await repo.set_daily(active.id, enabled=True, at=time(21, 0))
        await session.commit()

    delivered: list[int] = []

    async def deliver(*, user, kind, local_today) -> None:
        delivered.append(user.telegram_id)

    # Only `222` is in the allowlist now; `111` was revoked.
    scheduler = SummaryScheduler(
        sessionmaker=schedule_sm,
        delivery=deliver,
        allowed_telegram_ids=frozenset({222}),
    )
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 19, 0))
    await scheduler.dispatch_due(now_utc)

    assert delivered == [222]
