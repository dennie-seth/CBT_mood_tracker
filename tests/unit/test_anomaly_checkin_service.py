"""AnomalyCheckinService.maybe_probe enforces gating BEFORE running detection.

Gating order (cheap → expensive):
1. checkins_enabled? (else: no-op)
2. quiet hours? (only between 08:00 and 22:00 in user tz)
3. cooldown — last probe < 24h ago? (no-op)
4. daily summary already fired today in user tz? (no-op — it covers
   the same ground)
5. detector finds an anomaly? (else: no-op, also stamps so we don't
   recompute next minute)

The test uses a fake repo + an injectable detector to exercise gating
without hitting Postgres or Anthropic.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd
import pytest
import pytz

from app.domain.models import User
from app.services.anomaly_checkin_service import AnomalyCheckinService
from app.services.anomaly_detector import Anomaly, AnomalyKind


@dataclass
class FakePrefs:
    user_id: int = 1
    checkins_enabled: bool = True
    checkins_last_sent_at: datetime | None = None
    daily_last_sent_date: date | None = None


@dataclass
class FakeScheduleRepo:
    prefs: FakePrefs
    stamped_at: datetime | None = None

    async def get(self, user_id: int) -> FakePrefs | None:
        return self.prefs if self.prefs.user_id == user_id else None

    async def stamp_checkin_sent(self, user_id: int, *, at: datetime) -> None:
        self.stamped_at = at
        self.prefs.checkins_last_sent_at = at


@dataclass
class FakeAnalysis:
    df: pd.DataFrame = field(default_factory=pd.DataFrame)

    async def daily_summary(self, user_id: int, start: date, end: date) -> pd.DataFrame:
        return self.df


@dataclass
class FakeDetector:
    anomalies: list[Anomaly] = field(default_factory=list)
    last_call: dict[str, Any] | None = None

    def detect(self, df: pd.DataFrame, *, today: date) -> list[Anomaly]:
        self.last_call = {"df_shape": df.shape, "today": today}
        return list(self.anomalies)


@dataclass
class SentMessage:
    chat_id: int
    text: str


@dataclass
class FakeBot:
    sent: list[SentMessage] = field(default_factory=list)

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append(SentMessage(chat_id=chat_id, text=text))


def _user(*, language: str = "en", tz_name: str = "UTC") -> User:
    u = User(telegram_id=42, display_name="Pat", timezone=tz_name, language=language)
    u.id = 1
    return u


def _utc(d: date, h: int, m: int = 0) -> datetime:
    return pytz.utc.localize(datetime.combine(d, time(h, m)))


# ---- gating -----------------------------------------------------------


@pytest.mark.asyncio
async def test_no_probe_when_checkins_disabled() -> None:
    prefs = FakePrefs(checkins_enabled=False)
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    detector = FakeDetector(anomalies=[
        Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
    ])
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=detector,
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    await svc.maybe_probe(_user(), now_utc=_utc(date(2026, 5, 4), 12))
    assert bot.sent == []
    assert repo.stamped_at is None
    assert detector.last_call is None  # detection not even attempted


@pytest.mark.asyncio
async def test_no_probe_during_quiet_hours_late_night() -> None:
    prefs = FakePrefs()
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    # 03:00 in UTC = 03:00 in user's tz (UTC), which is in the quiet window.
    await svc.maybe_probe(_user(), now_utc=_utc(date(2026, 5, 4), 3))
    assert bot.sent == []


@pytest.mark.asyncio
async def test_no_probe_within_24h_cooldown() -> None:
    last_sent = _utc(date(2026, 5, 4), 9)  # 9am today
    prefs = FakePrefs(checkins_last_sent_at=last_sent)
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    # 1 hour later — cooldown not elapsed
    await svc.maybe_probe(_user(), now_utc=last_sent + timedelta(hours=1))
    assert bot.sent == []


@pytest.mark.asyncio
async def test_no_probe_when_daily_already_fired_today() -> None:
    prefs = FakePrefs(daily_last_sent_date=date(2026, 5, 4))
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    await svc.maybe_probe(_user(), now_utc=_utc(date(2026, 5, 4), 14))
    assert bot.sent == []


@pytest.mark.asyncio
async def test_no_probe_when_no_anomaly() -> None:
    prefs = FakePrefs()
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[]),  # nothing detected
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    await svc.maybe_probe(_user(), now_utc=_utc(date(2026, 5, 4), 14))
    assert bot.sent == []
    # Don't stamp on no-detection; we want to retry later if state changes.
    assert repo.stamped_at is None


# ---- happy path -------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_sends_message_and_stamps_when_anomaly_detected() -> None:
    prefs = FakePrefs()
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    now = _utc(date(2026, 5, 4), 14)
    await svc.maybe_probe(_user(), now_utc=now)
    assert len(bot.sent) == 1
    assert bot.sent[0].chat_id == 42  # user.telegram_id
    # Concrete value shows up so the user knows what triggered it.
    assert "9" in bot.sent[0].text
    assert repo.stamped_at == now


@pytest.mark.asyncio
async def test_probe_picks_highest_priority_anomaly_when_multiple() -> None:
    prefs = FakePrefs()
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            # Already sorted by detector priority
            Anomaly(AnomalyKind.LOW_MOOD_STREAK, {
                "values": [3.0, 4.0, 3.0], "days": 3, "since": "2026-05-02",
            }),
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0}),
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    await svc.maybe_probe(_user(), now_utc=_utc(date(2026, 5, 4), 14))
    assert len(bot.sent) == 1
    text = bot.sent[0].text
    # Streak content must show up; spike content must not (only top one sent)
    assert "3" in text  # at least one of the streak values
    assert "9" not in text


@pytest.mark.asyncio
async def test_probe_renders_in_user_language() -> None:
    prefs = FakePrefs()
    repo = FakeScheduleRepo(prefs)
    bot = FakeBot()
    svc = AnomalyCheckinService(
        schedule_repo_factory=lambda s: repo,
        analysis_factory=lambda s: FakeAnalysis(),
        detector=FakeDetector(anomalies=[
            Anomaly(AnomalyKind.ANXIETY_SPIKE, {"value": 9.0})
        ]),
        sessionmaker=_dummy_sm(),
        bot=bot,
    )
    await svc.maybe_probe(
        _user(language="ru"), now_utc=_utc(date(2026, 5, 4), 14)
    )
    text = bot.sent[0].text
    # Some Cyrillic letter from the RU template should be present.
    assert any(ord(ch) >= 0x0400 and ord(ch) <= 0x04FF for ch in text), (
        f"expected Russian characters in {text!r}"
    )


# ---- helpers ----------------------------------------------------------


def _dummy_sm() -> Callable[[], Any]:
    """Sessionmaker stub. The service uses it as a context manager. The
    fake repo/analysis factories don't actually consume the session, so a
    bare async-context-manager that yields None is enough."""
    class _Sess:
        async def __aenter__(self) -> _Sess:
            return self
        async def __aexit__(self, *exc) -> None:
            return None
        async def commit(self) -> None:
            return None
    return lambda: _Sess()
