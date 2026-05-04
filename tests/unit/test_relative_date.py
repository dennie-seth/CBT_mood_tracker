"""Parser for relative-date phrases used by /backfill.

Accepts: ISO date `YYYY-MM-DD`, `today`, `yesterday`, `N days ago`,
`N day ago` (singular). Case-insensitive. Anything else → ValueError.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
import pytz

from app.services.time import parse_relative_date


def _fixed_now(year: int, month: int, day: int, hour: int = 12, tz: str = "UTC"):
    """Return a context manager freezing now_in_tz to the given moment."""
    fixed = pytz.timezone(tz).localize(datetime(year, month, day, hour))

    def _stub(_tz: str):
        return fixed.astimezone(pytz.timezone(_tz))

    return patch("app.services.time.now_in_tz", side_effect=_stub)


def test_today() -> None:
    with _fixed_now(2026, 5, 4):
        assert parse_relative_date("today", "UTC") == date(2026, 5, 4)
        assert parse_relative_date("Today", "UTC") == date(2026, 5, 4)


def test_yesterday() -> None:
    with _fixed_now(2026, 5, 4):
        assert parse_relative_date("yesterday", "UTC") == date(2026, 5, 3)
        assert parse_relative_date("YESTERDAY", "UTC") == date(2026, 5, 3)


def test_n_days_ago() -> None:
    with _fixed_now(2026, 5, 10):
        assert parse_relative_date("3 days ago", "UTC") == date(2026, 5, 7)
        assert parse_relative_date("1 day ago", "UTC") == date(2026, 5, 9)
        assert parse_relative_date("0 days ago", "UTC") == date(2026, 5, 10)
        assert parse_relative_date("10 days ago", "UTC") == date(2026, 4, 30)


def test_iso_date() -> None:
    assert parse_relative_date("2026-05-04", "UTC") == date(2026, 5, 4)
    assert parse_relative_date("2024-02-29", "UTC") == date(2024, 2, 29)


def test_iso_date_does_not_use_now() -> None:
    """ISO dates are absolute — `today`'s value mustn't shift them."""
    with _fixed_now(2026, 5, 4):
        assert parse_relative_date("2024-01-01", "UTC") == date(2024, 1, 1)


def test_respects_user_timezone_for_today() -> None:
    """`today` is the user's local today, not UTC's."""
    # 23:30 UTC on May 4 == 09:30 May 5 in Auckland (UTC+10/+13).
    with _fixed_now(2026, 5, 4, hour=23):
        assert parse_relative_date("today", "Pacific/Auckland") == date(2026, 5, 5)
        assert parse_relative_date("today", "UTC") == date(2026, 5, 4)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "tomorrow",  # we don't accept future dates for backfill
        "1 day from now",
        "lots of days ago",
        "-1 days ago",
        "abc",
        "2026-13-01",  # invalid month
        "2026/05/04",  # wrong separator
    ],
)
def test_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_relative_date(raw, "UTC")


def test_rejects_future_iso_date() -> None:
    """Backfill is for the past. Future-dated entries are almost certainly typos."""
    with _fixed_now(2026, 5, 4):
        with pytest.raises(ValueError, match="future"):
            parse_relative_date("2026-12-31", "UTC")
