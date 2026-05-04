from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
import pytz

from app.infrastructure.schedule_models import SchedulePrefs
from app.services.schedule_service import is_daily_due, is_weekly_due


def _prefs(**overrides) -> SchedulePrefs:
    """Lightweight in-memory SchedulePrefs (no DB round-trip)."""
    base = dict(
        user_id=1,
        daily_enabled=False,
        daily_at=None,
        daily_last_sent_date=None,
        weekly_enabled=False,
        weekly_weekday=None,
        weekly_at=None,
        weekly_last_sent_date=None,
    )
    base.update(overrides)
    return SchedulePrefs(**base)


def _local(tz: str, *args) -> datetime:
    return pytz.timezone(tz).localize(datetime(*args))


# --- is_daily_due ---

def test_disabled_is_never_due() -> None:
    p = _prefs(daily_enabled=False, daily_at=time(21, 0))
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 22, 0)) is False


def test_enabled_but_no_time_is_never_due() -> None:
    p = _prefs(daily_enabled=True, daily_at=None)
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 22, 0)) is False


def test_before_set_time_is_not_due() -> None:
    p = _prefs(daily_enabled=True, daily_at=time(21, 0))
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 20, 59)) is False


def test_at_or_after_set_time_is_due() -> None:
    p = _prefs(daily_enabled=True, daily_at=time(21, 0))
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 21, 0)) is True
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 23, 30)) is True  # forgiving "missed" window


def test_already_sent_today_blocks_redelivery() -> None:
    p = _prefs(
        daily_enabled=True,
        daily_at=time(21, 0),
        daily_last_sent_date=date(2026, 5, 4),
    )
    assert is_daily_due(p, _local("UTC", 2026, 5, 4, 22, 0)) is False
    # …but the next day in user's tz should be due again.
    assert is_daily_due(p, _local("UTC", 2026, 5, 5, 21, 0)) is True


# --- is_weekly_due ---

def test_weekly_only_fires_on_configured_weekday() -> None:
    # 2026-05-04 is a Monday (ISO weekday 0).
    p = _prefs(weekly_enabled=True, weekly_weekday=6, weekly_at=time(21, 0))  # Sun
    assert is_weekly_due(p, _local("UTC", 2026, 5, 4, 21, 0)) is False  # Mon
    assert is_weekly_due(p, _local("UTC", 2026, 5, 10, 21, 0)) is True  # Sun


def test_weekly_dedup_within_same_date() -> None:
    p = _prefs(
        weekly_enabled=True,
        weekly_weekday=6,
        weekly_at=time(21, 0),
        weekly_last_sent_date=date(2026, 5, 10),
    )
    assert is_weekly_due(p, _local("UTC", 2026, 5, 10, 22, 0)) is False
    # Next Sunday should be due again.
    assert is_weekly_due(p, _local("UTC", 2026, 5, 17, 21, 0)) is True


# --- timezone correctness ---

def test_due_checker_respects_user_timezone() -> None:
    """Same wall-clock UTC produces different verdicts for users in different tz."""
    p = _prefs(daily_enabled=True, daily_at=time(21, 0))
    # 21:00 UTC == 23:00 in Berlin (UTC+2 DST), 14:00 in Los_Angeles.
    now_utc = pytz.utc.localize(datetime(2026, 5, 4, 21, 0))
    berlin_now = now_utc.astimezone(pytz.timezone("Europe/Berlin"))
    la_now = now_utc.astimezone(pytz.timezone("America/Los_Angeles"))

    # Berlin user: 23:00 ≥ 21:00 → due.
    assert is_daily_due(p, berlin_now) is True
    # LA user: 14:00 < 21:00 → not yet due.
    assert is_daily_due(p, la_now) is False
