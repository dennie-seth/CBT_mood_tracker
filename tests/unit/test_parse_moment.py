"""parse_moment: a typed point in time for migraine start/end.

Migraines last up to ~72h, so 'HH:MM within the last 24h' isn't enough.
Accepts:
  HH:MM / H.MM               → most recent such time (today or yesterday)
  yesterday HH:MM / вчера HH:MM
  DD.MM HH:MM                → this year (or last year if that'd be future)
  YYYY-MM-DD HH:MM
Future moments are rejected.
"""
from __future__ import annotations

from datetime import datetime

import pytest
import pytz

from app.services.time import parse_moment

TZ = pytz.timezone("Europe/Berlin")
NOW = TZ.localize(datetime(2026, 10, 8, 15, 0))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09:30", datetime(2026, 10, 8, 9, 30)),
        ("22:00", datetime(2026, 10, 7, 22, 0)),
        ("yesterday 9:15", datetime(2026, 10, 7, 9, 15)),
        ("Yesterday 23:59", datetime(2026, 10, 7, 23, 59)),
        ("вчера 07:00", datetime(2026, 10, 7, 7, 0)),
        ("06.10 18:30", datetime(2026, 10, 6, 18, 30)),
        ("6.10 8:05", datetime(2026, 10, 6, 8, 5)),
        ("2026-10-05 21:00", datetime(2026, 10, 5, 21, 0)),
        ("  2026-10-05   21:00 ", datetime(2026, 10, 5, 21, 0)),
    ],
)
def test_accepted_forms(raw: str, expected: datetime) -> None:
    assert parse_moment(raw, NOW) == TZ.localize(expected)


def test_day_month_in_future_means_last_year() -> None:
    assert parse_moment("24.12 10:00", NOW) == TZ.localize(datetime(2025, 12, 24, 10, 0))


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "soon",
        "2026-10-09 10:00",  # future
        "yesterday",  # no time
        "31.02 10:00",  # no such date
        "2026-13-01 10:00",
        "yesterday 25:00",
    ],
)
def test_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_moment(raw, NOW)
