"""Proactive anomaly check-ins.

Scheduled tick path (piggybacks SummaryScheduler):
  every minute, for users with `schedule_prefs.checkins_enabled`,
  call `AnomalyCheckinService.maybe_probe(user, now_utc)`.

Gating order is intentionally cheap → expensive so most ticks abort
early without touching the DB beyond loading prefs:

  1. checkins_enabled?
  2. quiet hours? (08:00 ≤ local time < 22:00)
  3. cooldown? (>= 24 h since last probe)
  4. daily summary already fired today in user tz?
  5. detector finds an anomaly?
  6. send + stamp.

Idempotency: stamp BEFORE send. A failed Telegram send = the user
misses *one* probe — that's strictly better than re-sending the same
"heads up" every minute until it succeeds.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any, Protocol

import pytz
import structlog

from app.bot.i18n import t
from app.domain.models import User
from app.services.anomaly_detector import (
    Anomaly,
    AnomalyDetector,
    AnomalyKind,
)

log = structlog.get_logger(__name__)

_QUIET_START = time(8, 0)
_QUIET_END = time(22, 0)
_COOLDOWN = timedelta(hours=24)
# How many days of history the detector looks at — generous enough to
# capture the longest streak (3 days) plus a little buffer for missing
# logs without paginating.
_LOOKBACK_DAYS = 7


class _BotLike(Protocol):
    async def send_message(self, chat_id: int, text: str) -> Any: ...


class AnomalyCheckinService:
    """Composed by main.py with the production sessionmaker + bot. Tests
    inject fakes via the *_factory hooks so the service stays unit-testable
    without Postgres or Anthropic."""

    def __init__(
        self,
        *,
        sessionmaker: Callable[[], Any],
        schedule_repo_factory: Callable[[Any], Any],
        analysis_factory: Callable[[Any], Any],
        detector: AnomalyDetector,
        bot: _BotLike,
    ) -> None:
        self._sm = sessionmaker
        self._schedule_repo_factory = schedule_repo_factory
        self._analysis_factory = analysis_factory
        self._detector = detector
        self._bot = bot

    async def maybe_probe(self, user: User, *, now_utc: datetime) -> None:
        if now_utc.tzinfo is None:
            now_utc = pytz.utc.localize(now_utc)
        local = now_utc.astimezone(pytz.timezone(user.timezone))

        # Quiet hours: cheap, no DB.
        if not (_QUIET_START <= local.time() < _QUIET_END):
            return

        async with self._sm() as session:
            schedule_repo = self._schedule_repo_factory(session)
            prefs = await schedule_repo.get(user.id)
            if prefs is None or not prefs.checkins_enabled:
                return

            # Cooldown.
            last = getattr(prefs, "checkins_last_sent_at", None)
            if last is not None:
                if last.tzinfo is None:
                    last = pytz.utc.localize(last)
                if now_utc - last < _COOLDOWN:
                    return

            # Skip if today's daily summary already covered the same ground.
            if prefs.daily_last_sent_date == local.date():
                return

            analysis = self._analysis_factory(session)
            start = local.date() - timedelta(days=_LOOKBACK_DAYS - 1)
            df = await analysis.daily_summary(user.id, start, local.date())
            anomalies = self._detector.detect(df, today=local.date())
            if not anomalies:
                # Don't stamp — recompute next tick is cheap and we'd rather
                # surface a freshly-arriving anomaly than wait 24 h.
                return

            # Stamp first (idempotency); pick highest-priority anomaly.
            await schedule_repo.stamp_checkin_sent(user.id, at=now_utc)
            await session.commit()

        text = self._render(anomalies[0], user.language)
        try:
            await self._bot.send_message(chat_id=user.telegram_id, text=text)
        except Exception as exc:
            log.warning(
                "checkin_send_failed",
                user_id=user.id,
                kind=anomalies[0].kind,
                error=str(exc),
            )
            return
        log.info(
            "checkin_sent",
            user_id=user.id,
            kind=anomalies[0].kind,
        )

    @staticmethod
    def _render(anomaly: Anomaly, lang: str) -> str:
        if anomaly.kind == AnomalyKind.LOW_MOOD_STREAK:
            return t(
                lang, "checkin.low_mood_streak",
                days=anomaly.summary["days"],
                values=", ".join(_fmt(v) for v in anomaly.summary["values"]),
            )
        if anomaly.kind == AnomalyKind.SLEEP_CRASH:
            return t(
                lang, "checkin.sleep_crash",
                days=anomaly.summary["days"],
                values=", ".join(_fmt(v) for v in anomaly.summary["values"]),
            )
        # ANXIETY_SPIKE
        return t(
            lang, "checkin.anxiety_spike",
            value=_fmt(anomaly.summary["value"]),
        )


def _fmt(v: float) -> str:
    """Drop trailing .0 on whole numbers; one decimal otherwise."""
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.1f}"
