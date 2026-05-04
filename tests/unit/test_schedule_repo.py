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


# --- Regression: enabling at a past time-of-day must not fire same day ---

async def test_set_daily_enabling_after_set_time_suppresses_today(schedule_sm) -> None:
    """User runs /dailyat 09:00 at 23:00 local. The scheduler's `>=` rule
    would otherwise fire 1 minute later. Suppress same-day delivery so the
    first one lands tomorrow at 09:00."""
    from datetime import date, datetime

    import pytz

    user = await _make_user(schedule_sm)
    now_local = pytz.timezone("Europe/Berlin").localize(datetime(2026, 5, 4, 23, 0))
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(9, 0), now_local=now_local)
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date == date(2026, 5, 4)


async def test_set_daily_enabling_before_set_time_leaves_last_sent_none(schedule_sm) -> None:
    """User runs /dailyat 21:00 at 08:00 local. The first delivery should
    happen TODAY at 21:00, so no suppression."""
    from datetime import datetime

    import pytz

    user = await _make_user(schedule_sm)
    now_local = pytz.timezone("Europe/Berlin").localize(datetime(2026, 5, 4, 8, 0))
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(user.id, enabled=True, at=time(21, 0), now_local=now_local)
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date is None


async def test_set_weekly_suppression_works_only_when_weekday_matches(schedule_sm) -> None:
    """If today IS the configured weekday and the time has passed, suppress.
    Otherwise leave last_sent_date alone — the next due day is in the future
    and there's no risk of an immediate fire."""
    from datetime import date, datetime

    import pytz

    user = await _make_user(schedule_sm)
    # 2026-05-10 is Sunday (ISO weekday 6). Set weekly to Sun 09:00 at 23:00 local.
    sun_evening = pytz.timezone("UTC").localize(datetime(2026, 5, 10, 23, 0))
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_weekly(
            user.id, enabled=True, weekday=6, at=time(9, 0), now_local=sun_evening
        )
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.weekly_last_sent_date == date(2026, 5, 10)

    # But on Monday after configuring for Sunday, the next due is six days away — leave it None.
    user2 = await _make_user(schedule_sm, telegram_id=2)
    mon_evening = pytz.timezone("UTC").localize(datetime(2026, 5, 11, 23, 0))
    async with schedule_sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_weekly(
            user2.id, enabled=True, weekday=6, at=time(9, 0), now_local=mon_evening
        )
        await session.commit()

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user2.id)
    assert prefs is not None
    assert prefs.weekly_last_sent_date is None
