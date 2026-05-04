from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytz

_DAYS_AGO_RE = re.compile(r"^(\d+)\s+days?\s+ago$")


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(tz=pytz.timezone(tz_name))


def today_in_tz(tz_name: str) -> date:
    return now_in_tz(tz_name).date()


def to_user_date(dt: datetime, tz_name: str) -> date:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone(tz_name)).date()


def parse_period(period: str, tz_name: str) -> tuple[date, date]:
    """Parse '7d' / '30d' / '90d' / 'all' into (start, end) inclusive dates.

    'all' is represented by start = 1970-01-01.
    """
    today = today_in_tz(tz_name)
    p = period.strip().lower()
    if p == "all":
        return date(1970, 1, 1), today
    if p.endswith("d"):
        try:
            days = int(p[:-1])
        except ValueError as e:
            raise ValueError(f"Invalid period: {period}") from e
        if days <= 0:
            raise ValueError(f"Period must be positive: {period}")
        return today - timedelta(days=days - 1), today
    raise ValueError(f"Unknown period: {period}. Use 7d, 30d, 90d or all.")


def parse_relative_date(raw: str, tz_name: str) -> date:
    """Parse a relaxed date phrase into an absolute `date` in the user's tz.

    Accepts:
      - `today` / `yesterday` (case-insensitive)
      - `N days ago` / `N day ago` (case-insensitive)
      - ISO date `YYYY-MM-DD` (absolute, no future allowed)

    Raises ValueError for anything else, and for future dates (backfill is
    for the past — a future date is almost certainly a typo).
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"empty or non-string date: {raw!r}")
    s = raw.strip().lower()

    if s == "today":
        return now_in_tz(tz_name).date()
    if s == "yesterday":
        return now_in_tz(tz_name).date() - timedelta(days=1)

    m = _DAYS_AGO_RE.match(s)
    if m:
        n = int(m.group(1))
        return now_in_tz(tz_name).date() - timedelta(days=n)

    # ISO date — strict YYYY-MM-DD.
    try:
        parsed = date.fromisoformat(raw.strip())
    except ValueError as e:
        raise ValueError(
            f"unrecognised date {raw!r}; use YYYY-MM-DD, today, yesterday, or 'N days ago'"
        ) from e

    today = now_in_tz(tz_name).date()
    if parsed > today:
        raise ValueError(f"date {parsed.isoformat()} is in the future; backfill is for past entries")
    return parsed
