from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time
from typing import Literal

import pytz
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.infrastructure.schedule_models import SchedulePrefs

log = structlog.get_logger(__name__)

SummaryKind = Literal["daily", "weekly"]
DeliveryFn = Callable[..., Awaitable[None]]
CheckinProbeFn = Callable[..., Awaitable[None]]

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]?\d)$")
_WEEKDAY_TO_ISO: dict[str, int] = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}
_ISO_TO_WEEKDAY: dict[int, str] = {v: k for k, v in _WEEKDAY_TO_ISO.items()}


def parse_time(raw: str) -> time:
    """Parse 'HH:MM' (24-hour) into a `datetime.time`. Strict; raises ValueError."""
    if not isinstance(raw, str):
        raise ValueError("time must be a string")
    m = _TIME_RE.match(raw.strip())
    if not m:
        raise ValueError(f"invalid time {raw!r}; expected HH:MM in 24-hour")
    return time(int(m.group(1)), int(m.group(2)))


def parse_weekday(raw: str) -> int:
    """Parse short weekday name (mon..sun, case-insensitive) → ISO 0..6."""
    if not isinstance(raw, str):
        raise ValueError("weekday must be a string")
    key = raw.strip().lower()
    if key not in _WEEKDAY_TO_ISO:
        raise ValueError(
            f"invalid weekday {raw!r}; expected one of {', '.join(_WEEKDAY_TO_ISO)}"
        )
    return _WEEKDAY_TO_ISO[key]


def format_weekday(iso: int) -> str:
    """0..6 → 'mon'..'sun'."""
    return _ISO_TO_WEEKDAY[iso]


def parse_weekly_args(raw: str) -> tuple[int, time]:
    """Parse '<weekday> <HH:MM>' (e.g. 'sun 21:00') → (iso_weekday, time)."""
    parts = raw.strip().split()
    if len(parts) != 2:
        raise ValueError(
            f"expected '<weekday> <HH:MM>' (e.g. 'sun 21:00'), got {raw!r}"
        )
    return parse_weekday(parts[0]), parse_time(parts[1])


def is_daily_due(prefs: SchedulePrefs, now_local: datetime) -> bool:
    """Pure check: is the daily summary due *now* in the user's timezone?

    `now_local` is a tz-aware `datetime` already converted to the user's
    timezone. We don't take `pytz.timezone(user.timezone)` here so this
    function stays IO-free and easy to test.
    """
    if not prefs.daily_enabled or prefs.daily_at is None:
        return False
    today = now_local.date()
    if prefs.daily_last_sent_date == today:
        return False
    # `>=` keeps the check forgiving: if the bot was down at the trigger
    # minute, the next tick still fires today.
    return now_local.time() >= prefs.daily_at


def is_weekly_due(prefs: SchedulePrefs, now_local: datetime) -> bool:
    if (
        not prefs.weekly_enabled
        or prefs.weekly_at is None
        or prefs.weekly_weekday is None
    ):
        return False
    if now_local.weekday() != prefs.weekly_weekday:
        return False
    today = now_local.date()
    if prefs.weekly_last_sent_date == today:
        return False
    return now_local.time() >= prefs.weekly_at


class SummaryScheduler:
    """Once-per-minute tick that dispatches due summaries.

    The actual delivery (build prompt, call Haiku, send via Bot, stamp
    last-sent) is injected via `delivery` so this class is testable
    without mocks of AiService / Bot.
    """

    TICK_INTERVAL_SECONDS = 60
    MAX_CONCURRENT_DELIVERIES = 8

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        delivery: DeliveryFn,
        allowed_telegram_ids: frozenset[int] | None = None,
        checkin_probe: CheckinProbeFn | None = None,
    ) -> None:
        self._sm = sessionmaker
        self._delivery = delivery
        self._checkin_probe = checkin_probe
        # `None` means "no allowlist enforcement here" — used in older tests and
        # equivalent to allowing all loaded users. Production passes the same
        # frozenset that the auth middleware uses.
        self._allowed_ids = allowed_telegram_ids
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DELIVERIES)
        self._task: asyncio.Task[None] | None = None

    async def dispatch_due(self, now_utc: datetime) -> None:
        if now_utc.tzinfo is None:
            now_utc = pytz.utc.localize(now_utc)

        async with self._sm() as session:
            rows = await SqlScheduleRepository(session).list_enabled()

        coros: list[Awaitable[None]] = []
        for prefs, user in rows:
            # Re-check the allowlist on every tick. The scheduler runs OUTSIDE
            # aiogram middleware, so removing a user from ALLOWED_TELEGRAM_IDS
            # would otherwise leave proactive Haiku summaries flowing.
            if (
                self._allowed_ids is not None
                and user.telegram_id not in self._allowed_ids
            ):
                log.warning(
                    "scheduler_skipping_revoked_user",
                    telegram_id=user.telegram_id,
                    user_id=user.id,
                )
                continue
            local = now_utc.astimezone(pytz.timezone(user.timezone))
            if is_daily_due(prefs, local):
                coros.append(
                    self._safe_deliver(user=user, kind="daily", local_today=local.date())
                )
            if is_weekly_due(prefs, local):
                coros.append(
                    self._safe_deliver(user=user, kind="weekly", local_today=local.date())
                )
            if self._checkin_probe is not None and prefs.checkins_enabled:
                coros.append(self._safe_probe(user=user, now_utc=now_utc))

        if coros:
            await asyncio.gather(*coros, return_exceptions=False)

    async def _safe_deliver(self, *, user: User, kind: SummaryKind, local_today: date) -> None:
        async with self._semaphore:  # cap fan-out so a big user base can't stampede Anthropic/Telegram
            try:
                await self._delivery(user=user, kind=kind, local_today=local_today)
            except Exception as exc:
                log.warning(
                    "summary_delivery_failed",
                    user_id=user.id,
                    kind=kind,
                    error=str(exc),
                )

    async def _safe_probe(self, *, user: User, now_utc: datetime) -> None:
        async with self._semaphore:
            try:
                await self._checkin_probe(user=user, now_utc=now_utc)  # type: ignore[misc]
            except Exception as exc:
                log.warning(
                    "checkin_probe_failed",
                    user_id=user.id,
                    error=str(exc),
                )

    async def run(self) -> None:
        """Long-running tick loop. Cancel the task to stop."""
        log.info("summary_scheduler_started", interval=self.TICK_INTERVAL_SECONDS)
        try:
            while True:
                try:
                    await self.dispatch_due(datetime.now(tz=UTC))
                except Exception as exc:
                    # A tick failure (e.g. transient DB error) must not kill the loop.
                    log.warning("summary_tick_failed", error=str(exc))
                await asyncio.sleep(self.TICK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            log.info("summary_scheduler_stopped")
            raise

    def start(self) -> asyncio.Task[None]:
        if self._task is not None and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self.run(), name="summary_scheduler")
        return self._task

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
