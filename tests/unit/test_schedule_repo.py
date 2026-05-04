from __future__ import annotations

from datetime import time

from sqlalchemy import select

from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.infrastructure.schedule_models import SchedulePrefs


_NEXT_USER_ID = [1]


async def _make_user(sm, telegram_id: int = 1, tz: str = "UTC") -> User:
    async with sm() as session:
        # SQLite doesn't auto-increment BIGINT PRIMARY KEY (Postgres does);
        # we assign explicitly per-test so the production model stays clean.
        uid = _NEXT_USER_ID[0]
        _NEXT_USER_ID[0] += 1
        u = User(id=uid, telegram_id=telegram_id, display_name="t", timezone=tz)
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


async def test_get_returns_none_when_absent(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        assert await repo.get(user.id) is None


async def test_set_daily_creates_row_then_get_returns_it(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0))
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_enabled is True
    assert prefs.daily_at == time(21, 0)
    assert prefs.weekly_enabled is False


async def test_set_weekly_does_not_clobber_daily(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0))
        await repo.set_weekly(user.id, enabled=True, weekday=6, at=time(20, 0))
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_enabled is True
    assert prefs.daily_at == time(21, 0)
    assert prefs.weekly_enabled is True
    assert prefs.weekly_weekday == 6
    assert prefs.weekly_at == time(20, 0)


async def test_disable_daily_keeps_weekly(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0))
        await repo.set_weekly(user.id, enabled=True, weekday=6, at=time(20, 0))
        await repo.set_daily(user.id, enabled=False)
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_enabled is False
    assert prefs.weekly_enabled is True


async def test_list_enabled_returns_users_and_skips_disabled(schedule_sm) -> None:
    u1 = await _make_user(schedule_sm, telegram_id=1, tz="UTC")
    u2 = await _make_user(schedule_sm, telegram_id=2, tz="Europe/Berlin")
    u3 = await _make_user(schedule_sm, telegram_id=3, tz="UTC")

    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(u1.id, enabled=True, at=time(21, 0))
        await repo.set_weekly(u2.id, enabled=True, weekday=6, at=time(20, 0))
        # u3 has a row but everything is off.
        await repo.set_daily(u3.id, enabled=False)
        await session.commit()

    async with schedule_sm() as session:
        rows = await SqlScheduleRepository(session).list_enabled()

    user_ids = sorted(user.id for prefs, user in rows)
    assert user_ids == [u1.id, u2.id]
    # The User row is loaded so dispatch can read .timezone / .telegram_id without lazy-load.
    by_id = {user.id: user for prefs, user in rows}
    assert by_id[u2.id].timezone == "Europe/Berlin"


async def test_stamp_daily_sent_persists(schedule_sm) -> None:
    from datetime import date

    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0))
        await repo.stamp_daily_sent(user.id, on=date(2026, 5, 4))
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date == date(2026, 5, 4)
