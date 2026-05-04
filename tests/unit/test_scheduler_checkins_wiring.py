"""SummaryScheduler dispatches the optional checkin probe alongside
daily/weekly summaries — only for users with `checkins_enabled` and
only when the probe callable is supplied. The allowlist still applies.
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


async def test_probe_called_for_checkins_users(schedule_sm) -> None:
    """One user has checkins on, another off; only the first gets probed."""
    on_user = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="UTC")
    off_user = await _seed_user(schedule_sm, id=2, telegram_id=222, tz="UTC")
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_checkins(on_user.id, enabled=True)
        # off_user gets a daily so list_enabled finds them, but no checkins.
        await repo.set_daily(off_user.id, enabled=True, at=time(21, 0))
        await session.commit()

    probe = AsyncMock()
    delivery = AsyncMock()
    scheduler = SummaryScheduler(
        sessionmaker=schedule_sm,
        delivery=delivery,
        checkin_probe=probe,
    )
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 12, 0))
    await scheduler.dispatch_due(now_utc)

    assert probe.await_count == 1
    args, kwargs = probe.call_args
    assert kwargs["user"].telegram_id == 111
    assert kwargs["now_utc"] == now_utc


async def test_probe_skipped_when_no_callback_provided(schedule_sm) -> None:
    """Backwards-compat: SummaryScheduler with no checkin_probe still ticks."""
    user = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="UTC")
    async with schedule_sm() as session:
        await SqlScheduleRepository(session).set_checkins(user.id, enabled=True)
        await session.commit()

    delivery = AsyncMock()
    scheduler = SummaryScheduler(sessionmaker=schedule_sm, delivery=delivery)
    await scheduler.dispatch_due(pytz.utc.localize(datetime(2026, 5, 4, 12, 0)))
    # Tick should run cleanly with no checkin handler.
    assert delivery.await_count == 0


async def test_probe_skipped_for_revoked_user(schedule_sm) -> None:
    """Allowlist applies to checkins too — revoked users get nothing."""
    revoked = await _seed_user(schedule_sm, id=1, telegram_id=111, tz="UTC")
    async with schedule_sm() as session:
        await SqlScheduleRepository(session).set_checkins(revoked.id, enabled=True)
        await session.commit()

    probe = AsyncMock()
    scheduler = SummaryScheduler(
        sessionmaker=schedule_sm,
        delivery=AsyncMock(),
        allowed_telegram_ids=frozenset({999}),  # revoked
        checkin_probe=probe,
    )
    await scheduler.dispatch_due(pytz.utc.localize(datetime(2026, 5, 4, 12, 0)))
    assert probe.await_count == 0
