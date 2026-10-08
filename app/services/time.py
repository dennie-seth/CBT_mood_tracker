from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytz

_DAYS_AGO_RE = re.compile(r"^(\d+)\s+days?\s+ago$")
_CLOCK_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")


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


def parse_clock_time(raw: str, now_local: datetime) -> datetime:
    """Parse a typed 'HH:MM' (or 'H.MM') into an aware datetime in the tz of
    `now_local`.

    Means the most recent such moment: today if it's not later than now,
    otherwise yesterday (an attack can't start in the future). Raises
    ValueError on anything else.
    """
    m = _CLOCK_RE.match(raw.strip()) if isinstance(raw, str) else None
    if not m:
        raise ValueError(f"unrecognised time {raw!r}; use HH:MM")
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"time out of range: {raw!r}")
    tz = now_local.tzinfo
    naive = now_local.replace(tzinfo=None, hour=hour, minute=minute, second=0, microsecond=0)
    if naive > now_local.replace(tzinfo=None):
        naive -= timedelta(days=1)
    # pytz zones need localize() to pick the right DST offset for that date.
    if isinstance(tz, pytz.BaseTzInfo):
        return tz.localize(naive)
    return naive.replace(tzinfo=tz)


_YESTERDAY_WORDS = ("yesterday", "вчера")
_DAY_MONTH_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})$")


def parse_moment(raw: str, now_local: datetime) -> datetime:
    """Parse a typed point in time (migraine start/end) in the tz of `now_local`.

    Accepts `HH:MM` (most recent such time), `yesterday HH:MM` / `вчера HH:MM`,
    `DD.MM HH:MM` (this year, or last year if that would be in the future)
    and `YYYY-MM-DD HH:MM`. Rejects future moments. Raises ValueError.
    """
    parts = raw.split() if isinstance(raw, str) else []
    if len(parts) == 1:
        return parse_clock_time(parts[0], now_local)
    if len(parts) != 2:
        raise ValueError(f"unrecognised moment {raw!r}")
    day_raw, clock_raw = parts
    m = _CLOCK_RE.match(clock_raw)
    if not m:
        raise ValueError(f"unrecognised time {clock_raw!r}; use HH:MM")
    hour, minute = int(m.group(1)), int(m.group(2))

    today = now_local.date()
    if day_raw.lower() in _YESTERDAY_WORDS:
        day = today - timedelta(days=1)
    elif dm := _DAY_MONTH_RE.match(day_raw):
        dd, mm = int(dm.group(1)), int(dm.group(2))
        day = date(today.year, mm, dd)  # ValueError on 31.02 etc.
        if day > today:
            day = date(today.year - 1, mm, dd)
    else:
        day = date.fromisoformat(day_raw)

    naive = datetime(day.year, day.month, day.day, hour, minute)  # range-checks
    tz = now_local.tzinfo
    moment = tz.localize(naive) if isinstance(tz, pytz.BaseTzInfo) else naive.replace(tzinfo=tz)
    if moment > now_local:
        raise ValueError(f"{raw!r} is in the future")
    return moment
