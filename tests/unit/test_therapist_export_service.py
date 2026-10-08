"""TherapistExportService composes a clinician-ready report payload.

The service does not draw the PDF — it just collects and decrypts the
slices a clinician needs to review:

- numeric daily summary (already produced by AnalysisService)
- thought records (situation/automatic/distortion/reframe), decrypted
- behavioral activation outcomes (predicted vs. actual, status, reason)
- notes + free-text body symptoms etc., decrypted

Each piece must come back already decrypted so PdfService can render
it without ever touching FernetCipher itself.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from app.domain.enums import MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import EntryService
from app.services.therapist_export_service import (
    TherapistExportService,
    TherapistReportData,
)
from tests.unit.fakes import FakeEntryRepo

FakeRepo = FakeEntryRepo

@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="Pat", timezone="UTC")
    u.id = 7
    return u


def _at(d: date, hour: int = 12) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=UTC).replace(
        hour=hour
    )


async def test_collect_empty_range_returns_empty_payload(cipher, user) -> None:
    repo = FakeRepo()
    svc = TherapistExportService(EntryService(repo, cipher))
    today = date(2026, 5, 4)
    data = await svc.collect(user, start=today - timedelta(days=6), end=today)

    assert isinstance(data, TherapistReportData)
    assert data.daily_df.empty
    assert data.thought_records == []
    assert data.ba_outcomes == []
    assert data.notes == []
    assert data.other_text == []


async def test_collect_decrypts_thought_records(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    today = date(2026, 5, 4)
    await es.create(
        user,
        MetricType.THOUGHT_RECORD,
        extra={
            "situation_text": "Big presentation tomorrow",
            "automatic_thought_text": "I'll embarrass myself",
            "distortion_text": "fortune-telling",
            "reframe_text": "I've prepared; outcome is uncertain, not catastrophic",
        },
        recorded_at=_at(today),
    )
    svc = TherapistExportService(es)
    data = await svc.collect(user, start=today - timedelta(days=6), end=today)

    assert len(data.thought_records) == 1
    tr = data.thought_records[0]
    assert tr.entry_date == today
    assert tr.situation == "Big presentation tomorrow"
    assert tr.automatic_thought == "I'll embarrass myself"
    assert tr.distortion == "fortune-telling"
    assert tr.reframe.startswith("I've prepared")


async def test_collect_ba_outcomes_capture_predicted_actual_and_status(
    cipher, user
) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    today = date(2026, 5, 4)
    # Done plan
    await es.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={
            "plan_text": "walk in the park",
            "planned_for": today.isoformat(),
            "predicted_effect": 7,
            "status": "done",
            "actual_effect": 8,
        },
        recorded_at=_at(today),
    )
    # Skipped plan
    await es.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={
            "plan_text": "call my brother",
            "planned_for": (today - timedelta(days=2)).isoformat(),
            "predicted_effect": 5,
            "status": "skipped",
            "skip_reason_text": "low energy",
        },
        recorded_at=_at(today - timedelta(days=2)),
    )
    # Still scheduled — should still surface so the clinician sees pending work
    await es.create(
        user,
        MetricType.ACTIVITY_PLAN,
        extra={
            "plan_text": "yoga",
            "planned_for": (today + timedelta(days=1)).isoformat(),
            "predicted_effect": 6,
            "status": "scheduled",
        },
        recorded_at=_at(today),
    )

    svc = TherapistExportService(es)
    data = await svc.collect(user, start=today - timedelta(days=6), end=today + timedelta(days=2))

    assert len(data.ba_outcomes) == 3
    by_text = {o.plan_text: o for o in data.ba_outcomes}
    walk = by_text["walk in the park"]
    assert walk.status == "done"
    assert walk.predicted_effect == 7
    assert walk.actual_effect == 8
    assert walk.skip_reason is None

    call = by_text["call my brother"]
    assert call.status == "skipped"
    assert call.skip_reason == "low energy"
    assert call.actual_effect is None

    yoga = by_text["yoga"]
    assert yoga.status == "scheduled"


async def test_collect_decrypts_notes_and_other_text(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    today = date(2026, 5, 4)
    await es.create(
        user, MetricType.NOTE, value_text="Felt tight in chest in the morning",
        recorded_at=_at(today),
    )
    await es.create(
        user, MetricType.SYMPTOM, value_text="headache, mild",
        recorded_at=_at(today - timedelta(days=1)),
    )
    await es.create(
        user, MetricType.TRIGGER, value_text="argument with manager",
        recorded_at=_at(today - timedelta(days=2)),
    )

    svc = TherapistExportService(es)
    data = await svc.collect(user, start=today - timedelta(days=6), end=today)

    assert [n.text for n in data.notes] == ["Felt tight in chest in the morning"]
    # other_text holds non-NOTE free-text fields, decrypted
    kinds = {(o.metric_type, o.text) for o in data.other_text}
    assert (MetricType.SYMPTOM, "headache, mild") in kinds
    assert (MetricType.TRIGGER, "argument with manager") in kinds


async def test_collect_includes_numeric_daily_summary(cipher, user) -> None:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    today = date(2026, 5, 4)
    await es.create(user, MetricType.MOOD, value_numeric=6, recorded_at=_at(today))
    await es.create(user, MetricType.MOOD, value_numeric=4, recorded_at=_at(today - timedelta(days=1)))
    await es.create(user, MetricType.SLEEP_QUALITY, value_numeric=7, recorded_at=_at(today))

    svc = TherapistExportService(es)
    data = await svc.collect(user, start=today - timedelta(days=6), end=today)

    assert not data.daily_df.empty
    assert "mood" in data.daily_df.columns
    assert "sleep_quality" in data.daily_df.columns


async def test_collect_includes_migraine_diary_decrypted(cipher, user) -> None:
    from app.services.migraine_service import MigraineService

    repo = FakeRepo()
    es = EntryService(repo, cipher)
    today = date(2026, 5, 4)
    onset = _at(today - timedelta(days=1), hour=9)
    ms = MigraineService(es, clock=lambda: _at(today, hour=12))
    a = await ms.start(
        user, intensity=5, started_at=onset, aura=True, symptoms=["nausea"],
        triggers=["sleep"], medication_text="sumatriptan 50", trigger_text="late night",
    )
    await ms.end(a.id, user, ended_at=onset + timedelta(hours=6), peak=8)
    await ms.update(a.id, user, relief=7)

    data = await TherapistExportService(es).collect(
        user, start=today - timedelta(days=6), end=today
    )

    assert len(data.migraines) == 1
    row = data.migraines[0]
    assert row.entry_date == today - timedelta(days=1)
    assert row.start_time == "09:00"
    assert row.duration_minutes == 360
    assert row.peak == 8
    assert row.aura is True
    assert row.symptoms == ["nausea"]
    assert row.triggers == ["sleep"]
    assert row.trigger_text == "late night"
    assert row.medication == "sumatriptan 50"
    assert row.relief == 7
    assert data.migraine_stats is not None
    assert data.migraine_stats.attacks == 1
