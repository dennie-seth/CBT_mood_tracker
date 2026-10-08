"""MigraineService: lifecycle + editing of migraine attacks.

One attack = one MIGRAINE entry. `value_numeric` = max(start, peak)
intensity (so it charts); episode details live in `extra`. All persistence
goes through EntryService, so `*_text` fields are encrypted and ownership is
enforced in one place. Failures raise MigraineError with a stable `code`
so the bot can show a friendly, translated message.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.enums import MetricType
from app.domain.models import User
from app.services.entry_service import EntryService
from app.services.migraine_service import (
    MigraineError,
    MigraineErrorCode,
    MigraineService,
)
from tests.unit.fakes import FakeEntryRepo

T0 = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)
NOW = T0 + timedelta(hours=6)


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC")
    u.id = 42
    return u


@pytest.fixture()
def other() -> User:
    u = User(telegram_id=2, display_name="o", timezone="UTC")
    u.id = 99
    return u


@pytest.fixture()
def repo() -> FakeEntryRepo:
    return FakeEntryRepo()


@pytest.fixture()
def es(repo, cipher) -> EntryService:
    return EntryService(repo, cipher)


@pytest.fixture()
def svc(es) -> MigraineService:
    return MigraineService(es, clock=lambda: NOW)


def _code(excinfo: pytest.ExceptionInfo[MigraineError]) -> MigraineErrorCode:
    return excinfo.value.code


# --- start ---

async def test_start_needs_only_intensity(svc, user) -> None:
    dto = await svc.start(user, intensity=6)

    assert dto.metric_type == MetricType.MIGRAINE
    assert dto.value_numeric == 6.0
    assert dto.recorded_at == NOW  # defaults to "now"
    assert dto.extra["status"] == "ongoing"
    assert dto.extra["started_at"] == NOW.isoformat()
    assert dto.extra["start_intensity"] == 6
    assert dto.extra["peak_intensity"] == 6
    assert dto.extra["aura"] is None  # unanswered, not "no"
    assert dto.extra["symptoms"] == []
    assert dto.extra["triggers"] == []


async def test_start_with_all_details_encrypts_free_text(svc, repo, user) -> None:
    dto = await svc.start(
        user, intensity=6, started_at=T0, aura=True,
        symptoms=["nausea", "light"], triggers=["sleep", "screens"],
        medication_text="ibuprofen 400", trigger_text="long call",
    )
    assert dto.extra["aura"] is True
    assert dto.extra["symptoms"] == ["nausea", "light"]
    assert dto.extra["triggers"] == ["sleep", "screens"]
    assert dto.extra["medication_text"] == "ibuprofen 400"
    assert dto.extra["trigger_text"] == "long call"

    raw = repo.rows[0].extra
    assert raw["medication_text"]["__enc__"] is True
    assert raw["trigger_text"]["__enc__"] is True
    assert "ibuprofen" not in str(raw) and "long call" not in str(raw)


async def test_start_date_follows_user_timezone(cipher) -> None:
    u = User(telegram_id=1, display_name="t", timezone="Europe/Berlin")
    u.id = 42
    late = datetime(2026, 10, 8, 23, 30, tzinfo=UTC)  # already Oct 9 in Berlin
    svc = MigraineService(EntryService(FakeEntryRepo(), cipher), clock=lambda: late)
    dto = await svc.start(u, intensity=5, started_at=late)
    assert dto.entry_date == date(2026, 10, 9)


@pytest.mark.parametrize("bad", [0, 11, -1])
async def test_start_rejects_out_of_range_intensity(svc, user, bad) -> None:
    with pytest.raises(MigraineError) as ei:
        await svc.start(user, intensity=bad)
    assert _code(ei) is MigraineErrorCode.BAD_SCALE


async def test_start_rejects_unknown_symptom_and_trigger(svc, user) -> None:
    with pytest.raises(MigraineError) as ei:
        await svc.start(user, intensity=5, symptoms=["dragons"])
    assert _code(ei) is MigraineErrorCode.UNKNOWN_SYMPTOM
    with pytest.raises(MigraineError) as ei:
        await svc.start(user, intensity=5, triggers=["moon"])
    assert _code(ei) is MigraineErrorCode.UNKNOWN_TRIGGER


async def test_start_rejects_future(svc, user) -> None:
    with pytest.raises(MigraineError) as ei:
        await svc.start(user, intensity=5, started_at=NOW + timedelta(hours=1))
    assert _code(ei) is MigraineErrorCode.IN_FUTURE


# --- update (works mid-attack and after) ---

async def test_update_details_one_at_a_time(svc, repo, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    await svc.update(a.id, user, aura=False)
    await svc.update(a.id, user, symptoms=["sound"])
    await svc.update(a.id, user, triggers=["stress"])
    await svc.update(a.id, user, medication_text="sumatriptan 50")
    dto = await svc.update(a.id, user, trigger_text="deadline")

    assert dto.extra["aura"] is False
    assert dto.extra["symptoms"] == ["sound"]
    assert dto.extra["triggers"] == ["stress"]
    assert dto.extra["medication_text"] == "sumatriptan 50"
    assert dto.extra["trigger_text"] == "deadline"
    assert dto.extra["status"] == "ongoing"
    assert repo.rows[0].extra["medication_text"]["__enc__"] is True


async def test_update_peak_raises_value_but_never_below_start(svc, user) -> None:
    a = await svc.start(user, intensity=6, started_at=T0)
    worse = await svc.update(a.id, user, peak=8)
    assert worse.value_numeric == 8.0
    assert worse.extra["peak_intensity"] == 8
    lower = await svc.update(a.id, user, peak=3)
    assert lower.value_numeric == 6.0


async def test_update_started_at_moves_day_bucket(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    moved = await svc.update(a.id, user, started_at=T0 - timedelta(days=1))
    assert moved.entry_date == date(2026, 10, 7)
    assert moved.recorded_at == T0 - timedelta(days=1)
    assert moved.extra["started_at"] == (T0 - timedelta(days=1)).isoformat()


async def test_update_started_at_recomputes_duration_of_ended_attack(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    await svc.end(a.id, user, ended_at=T0 + timedelta(hours=2))
    dto = await svc.update(a.id, user, started_at=T0 - timedelta(hours=1))
    assert dto.extra["duration_minutes"] == 180


async def test_update_started_at_after_end_rejected(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    await svc.end(a.id, user, ended_at=T0 + timedelta(hours=1))
    with pytest.raises(MigraineError) as ei:
        await svc.update(a.id, user, started_at=T0 + timedelta(hours=2))
    assert _code(ei) is MigraineErrorCode.END_BEFORE_START


async def test_update_ended_at_only_for_ended_attacks(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    with pytest.raises(MigraineError) as ei:
        await svc.update(a.id, user, ended_at=T0 + timedelta(hours=1))
    assert _code(ei) is MigraineErrorCode.NOT_ENDED

    await svc.end(a.id, user, ended_at=T0 + timedelta(hours=1))
    dto = await svc.update(a.id, user, ended_at=T0 + timedelta(hours=4))
    assert dto.extra["duration_minutes"] == 240


async def test_relief_requires_medication(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    with pytest.raises(MigraineError) as ei:
        await svc.update(a.id, user, relief=5)
    assert _code(ei) is MigraineErrorCode.RELIEF_WITHOUT_MEDICATION

    await svc.update(a.id, user, medication_text="ibuprofen")
    dto = await svc.update(a.id, user, relief=7)
    assert dto.extra["relief"] == 7


async def test_clearing_medication_also_clears_relief(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0, medication_text="x")
    await svc.update(a.id, user, relief=4)
    dto = await svc.update(a.id, user, medication_text=None)
    assert "medication_text" not in dto.extra
    assert "relief" not in dto.extra


async def test_update_refuses_other_users_attack(svc, user, other) -> None:
    a = await svc.start(user, intensity=5)
    with pytest.raises(MigraineError) as ei:
        await svc.update(a.id, other, aura=True)
    assert _code(ei) is MigraineErrorCode.NOT_FOUND


async def test_update_refuses_non_migraine_entry(svc, es, user) -> None:
    note = await es.create(user, MetricType.NOTE, value_text="hi")
    with pytest.raises(MigraineError) as ei:
        await svc.update(note.id, user, aura=True)
    assert _code(ei) is MigraineErrorCode.NOT_MIGRAINE


async def test_update_handles_v1_attack_without_new_keys(svc, es, user) -> None:
    """Attacks saved by the first version have no peak_intensity/triggers."""
    old = await es.create(
        user, MetricType.MIGRAINE, value_numeric=6, recorded_at=T0,
        extra={"status": "ongoing", "started_at": T0.isoformat(),
               "start_intensity": 6, "aura": False, "symptoms": []},
    )
    dto = await svc.update(old.id, user, triggers=["alcohol"])
    assert dto.extra["triggers"] == ["alcohol"]
    ended = await svc.end(old.id, user, ended_at=T0 + timedelta(hours=1), peak=7)
    assert ended.value_numeric == 7.0


# --- end / close_unknown_end ---

async def test_end_records_duration_and_peak(svc, user) -> None:
    a = await svc.start(user, intensity=4, started_at=T0)
    dto = await svc.end(a.id, user, ended_at=T0 + timedelta(hours=5, minutes=20), peak=8)
    assert dto.extra["status"] == "ended"
    assert dto.extra["ended_at"] == (T0 + timedelta(hours=5, minutes=20)).isoformat()
    assert dto.extra["duration_minutes"] == 320
    assert dto.value_numeric == 8.0


async def test_end_defaults_to_now_and_keeps_peak(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    await svc.update(a.id, user, peak=7)
    dto = await svc.end(a.id, user)
    assert dto.extra["ended_at"] == NOW.isoformat()
    assert dto.extra["duration_minutes"] == 360
    assert dto.value_numeric == 7.0


async def test_end_errors(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    with pytest.raises(MigraineError) as ei:
        await svc.end(a.id, user, ended_at=T0 - timedelta(minutes=1))
    assert _code(ei) is MigraineErrorCode.END_BEFORE_START
    with pytest.raises(MigraineError) as ei:
        await svc.end(a.id, user, ended_at=NOW + timedelta(hours=1))
    assert _code(ei) is MigraineErrorCode.IN_FUTURE

    await svc.end(a.id, user)
    with pytest.raises(MigraineError) as ei:
        await svc.end(a.id, user)
    assert _code(ei) is MigraineErrorCode.ALREADY_ENDED


async def test_close_unknown_end(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    dto = await svc.close_unknown_end(a.id, user)
    assert dto.extra["status"] == "ended"
    assert dto.extra["end_unknown"] is True
    assert "ended_at" not in dto.extra
    assert "duration_minutes" not in dto.extra


async def test_setting_end_time_later_clears_unknown_flag(svc, user) -> None:
    a = await svc.start(user, intensity=5, started_at=T0)
    await svc.close_unknown_end(a.id, user)
    dto = await svc.update(a.id, user, ended_at=T0 + timedelta(hours=2))
    assert "end_unknown" not in dto.extra
    assert dto.extra["duration_minutes"] == 120


# --- listing ---

async def test_list_open_returns_every_open_attack_up_to_30_days(svc, es, user, other) -> None:
    old = await svc.start(user, intensity=5, started_at=NOW - timedelta(days=10))
    new = await svc.start(user, intensity=5, started_at=T0)
    closed = await svc.start(user, intensity=5, started_at=T0 - timedelta(days=1))
    await svc.end(closed.id, user, ended_at=T0 - timedelta(hours=20))
    await svc.start(other, intensity=5, started_at=T0)
    # Plain numeric migraine (/backfill) has no status → never "open".
    await es.create(user, MetricType.MIGRAINE, value_numeric=4, recorded_at=T0)

    got = await svc.list_open(user.id, today=NOW.date())
    assert [d.id for d in got] == [old.id, new.id]


async def test_is_stale_after_72h(svc, user) -> None:
    fresh = await svc.start(user, intensity=5, started_at=NOW - timedelta(hours=71))
    stale = await svc.start(user, intensity=5, started_at=NOW - timedelta(hours=73))
    assert svc.is_stale(fresh) is False
    assert svc.is_stale(stale) is True


async def test_latest_returns_most_recent_attack_open_or_not(svc, user) -> None:
    assert await svc.latest(user.id, today=NOW.date()) is None
    a = await svc.start(user, intensity=5, started_at=T0 - timedelta(days=2))
    b = await svc.start(user, intensity=5, started_at=T0 - timedelta(days=1))
    await svc.end(b.id, user, ended_at=T0)
    got = await svc.latest(user.id, today=NOW.date())
    assert got is not None and got.id == b.id
    assert a.id != b.id


async def test_recent_medications_distinct_newest_first(svc, user, other) -> None:
    for i, med in enumerate(["ibuprofen 400", "sumatriptan 50", "Ibuprofen 400", "tea", None]):
        await svc.start(
            user, intensity=5, started_at=T0 - timedelta(days=10 - i), medication_text=med
        )
    await svc.start(other, intensity=5, started_at=T0, medication_text="secret")

    got = await svc.recent_medications(user.id, today=NOW.date(), limit=2)
    # Case-insensitive de-dup keeps the newest spelling.
    assert got == ["tea", "Ibuprofen 400"]


# --- delete ---

async def test_delete_removes_attack(svc, repo, user) -> None:
    a = await svc.start(user, intensity=5)
    await svc.delete(a.id, user)
    assert repo.rows == []


async def test_delete_refuses_non_migraine_and_other_users(svc, es, repo, user, other) -> None:
    note = await es.create(user, MetricType.NOTE, value_text="keep me")
    with pytest.raises(MigraineError) as ei:
        await svc.delete(note.id, user)
    assert _code(ei) is MigraineErrorCode.NOT_MIGRAINE

    a = await svc.start(user, intensity=5)
    with pytest.raises(MigraineError) as ei:
        await svc.delete(a.id, other)
    assert _code(ei) is MigraineErrorCode.NOT_FOUND
    assert len(repo.rows) == 2
