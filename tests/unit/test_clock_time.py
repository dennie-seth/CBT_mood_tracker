"""parse_clock_time: 'HH:MM' typed by the user → aware datetime in their tz.

Used for migraine start/end times. A time later than 'now' means
yesterday (you can't log an attack that starts in the future).
"""
from __future__ import annotations

from datetime import datetime

import pytest
import pytz

from app.services.time import parse_clock_time

TZ = pytz.timezone("Europe/Berlin")
NOW = TZ.localize(datetime(2026, 10, 8, 15, 0))


def test_earlier_today() -> None:
    got = parse_clock_time("09:30", NOW)
    assert got == TZ.localize(datetime(2026, 10, 8, 9, 30))


def test_single_digit_hour_and_dot_separator() -> None:
    assert parse_clock_time("9.05", NOW) == TZ.localize(datetime(2026, 10, 8, 9, 5))


def test_later_than_now_means_yesterday() -> None:
    got = parse_clock_time("22:00", NOW)
    assert got == TZ.localize(datetime(2026, 10, 7, 22, 0))


@pytest.mark.parametrize("raw", ["", "abc", "25:00", "12:60", "12", "12:3x"])
def test_invalid_raises(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_clock_time(raw, NOW)


def test_uses_offset_of_the_parsed_moment_across_dst() -> None:
    """Berlin leaves DST at 03:00 on 2026-10-25. At 10:00 (CET, +1) a typed
    01:30 the same morning was still CEST (+2)."""
    now = TZ.localize(datetime(2026, 10, 25, 10, 0))
    got = parse_clock_time("01:30", now)
    assert got.utcoffset() is not None
    assert got.utcoffset().total_seconds() == 2 * 3600
