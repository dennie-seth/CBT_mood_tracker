"""MigraineService: start/end lifecycle for migraine episodes.

An attack is one MIGRAINE entry. `value_numeric` holds the peak intensity
(so it charts); episode details live in `extra`. All persistence goes
through EntryService, so `*_text` fields are encrypted and ownership is
enforced in one place.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from app.domain.enums import MetricType
from app.domain.models import Entry, User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import EntryService
from app.services.migraine_service import MigraineService


class FakeRepo:
    def __init__(self) -> None:
        self.rows: list[Entry] = []
        self._next = 1

    async def add(self, entry: Entry) -> Entry:
        entry.id = self._next
        self._next += 1
        self.rows.append(entry)
        return entry

    async def list_range(self, user_id, start, end, metric_types=None):
        out = [
            r for r in self.rows
            if r.user_id == user_id and start <= r.entry_date <= end
        ]
        if metric_types:
            out = [r for r in out if r.metric_type in metric_types]
        return out

    async def daily_aggregates(self, *a, **kw):
        return []

    async def get_for_user(self, entry_id, user_id):
        for r in self.rows:
            if r.id == entry_id and r.user_id == user_id:
                return r
        return None

    async def exists(self, entry_id):
        return any(r.id == entry_id for r in self.rows)


@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="UTC")
    u.id = 42
    return u


T0 = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)


def _svc(cipher) -> tuple[MigraineService, FakeRepo, EntryService]:
    repo = FakeRepo()
    es = EntryService(repo, cipher)
    return MigraineService(es), repo, es


async def _start(svc: MigraineService, user: User, **kw):
    args = dict(
        started_at=T0,
        intensity=5,
        aura=False,
        symptoms=[],
        medication_text=None,
        trigger_text=None,
    )
    args.update(kw)
    return await svc.start(user, **args)


# --- start ---

async def test_start_creates_ongoing_migraine_entry(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(
        svc, user,
        intensity=6, aura=True, symptoms=["nausea", "light"],
        medication_text="ibuprofen 400", trigger_text="skipped lunch",
    )

    assert dto.metric_type == MetricType.MIGRAINE
    assert dto.value_numeric == 6.0
    assert dto.recorded_at == T0
    assert dto.extra["status"] == "ongoing"
    assert dto.extra["started_at"] == T0.isoformat()
    assert dto.extra["start_intensity"] == 6
    assert dto.extra["aura"] is True
    assert dto.extra["symptoms"] == ["nausea", "light"]
    assert dto.extra["medication_text"] == "ibuprofen 400"
    assert dto.extra["trigger_text"] == "skipped lunch"


async def test_start_encrypts_free_text_at_rest(cipher, user) -> None:
    svc, repo, _ = _svc(cipher)
    await _start(svc, user, medication_text="sumatriptan", trigger_text="red wine")

    raw = repo.rows[0].extra
    assert raw["medication_text"].get("__enc__") is True
    assert raw["trigger_text"].get("__enc__") is True
    assert "sumatriptan" not in str(raw)
    assert "red wine" not in str(raw)


async def test_start_omits_empty_optional_text(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user, medication_text=None, trigger_text="  ")
    assert "medication_text" not in dto.extra
    assert "trigger_text" not in dto.extra


async def test_start_date_follows_user_timezone(cipher) -> None:
    """23:30 UTC is already the next day in Berlin — the attack belongs there."""
    u = User(telegram_id=1, display_name="t", timezone="Europe/Berlin")
    u.id = 42
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, u, started_at=datetime(2026, 10, 8, 23, 30, tzinfo=UTC))
    assert dto.entry_date == date(2026, 10, 9)


@pytest.mark.parametrize("bad", [0, 11, -1])
async def test_start_rejects_out_of_range_intensity(cipher, user, bad) -> None:
    svc, _, _ = _svc(cipher)
    with pytest.raises(ValueError):
        await _start(svc, user, intensity=bad)


async def test_start_rejects_unknown_symptom(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    with pytest.raises(ValueError):
        await _start(svc, user, symptoms=["nausea", "dragons"])


# --- list_ongoing ---

async def test_list_ongoing_returns_only_open_attacks(cipher, user) -> None:
    svc, _, es = _svc(cipher)
    open_one = await _start(svc, user)
    closed = await _start(svc, user, started_at=T0 - timedelta(days=1))
    await svc.end(closed.id, user, ended_at=T0 - timedelta(hours=20), peak_intensity=5)
    # A plain numeric migraine (e.g. via /backfill) has no status → not "open".
    await es.create(user, MetricType.MIGRAINE, value_numeric=4, recorded_at=T0)

    got = await svc.list_ongoing(user.id, on_or_before=T0.date())
    assert [d.id for d in got] == [open_one.id]


async def test_list_ongoing_ignores_other_users(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    await _start(svc, other)
    assert await svc.list_ongoing(user.id, on_or_before=T0.date()) == []


# --- end ---

async def test_end_records_duration_peak_and_status(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user, intensity=4, medication_text="ibuprofen")

    ended = await svc.end(
        dto.id, user,
        ended_at=T0 + timedelta(hours=5, minutes=20),
        peak_intensity=8, relief=6,
    )

    assert ended.extra["status"] == "ended"
    assert ended.extra["ended_at"] == (T0 + timedelta(hours=5, minutes=20)).isoformat()
    assert ended.extra["duration_minutes"] == 320
    assert ended.extra["relief"] == 6
    assert ended.value_numeric == 8.0
    # Details captured at start survive the update (and stay decryptable).
    assert ended.extra["medication_text"] == "ibuprofen"
    assert ended.extra["start_intensity"] == 4


async def test_end_peak_never_below_start_intensity(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user, intensity=7)
    ended = await svc.end(dto.id, user, ended_at=T0 + timedelta(hours=1), peak_intensity=3)
    assert ended.value_numeric == 7.0


async def test_end_can_add_medication_taken_mid_attack(cipher, user) -> None:
    svc, repo, _ = _svc(cipher)
    dto = await _start(svc, user)
    ended = await svc.end(
        dto.id, user, ended_at=T0 + timedelta(hours=2), peak_intensity=6,
        medication_text="paracetamol", relief=4,
    )
    assert ended.extra["medication_text"] == "paracetamol"
    assert repo.rows[0].extra["medication_text"].get("__enc__") is True


async def test_end_rejects_relief_without_medication(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user)
    with pytest.raises(ValueError, match="medication"):
        await svc.end(dto.id, user, ended_at=T0 + timedelta(hours=1), peak_intensity=5, relief=5)


async def test_end_rejects_end_before_start(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user)
    with pytest.raises(ValueError, match="before"):
        await svc.end(dto.id, user, ended_at=T0 - timedelta(minutes=1), peak_intensity=5)


async def test_end_refuses_already_ended(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user)
    await svc.end(dto.id, user, ended_at=T0 + timedelta(hours=1), peak_intensity=5)
    with pytest.raises(ValueError, match="already"):
        await svc.end(dto.id, user, ended_at=T0 + timedelta(hours=2), peak_intensity=5)


async def test_end_refuses_non_migraine_entry(cipher, user) -> None:
    svc, _, es = _svc(cipher)
    note = await es.create(user, MetricType.NOTE, value_text="not a migraine")
    with pytest.raises(ValueError, match="not a migraine"):
        await svc.end(note.id, user, ended_at=T0, peak_intensity=5)


async def test_end_refuses_other_users_attack(cipher, user) -> None:
    svc, _, _ = _svc(cipher)
    dto = await _start(svc, user)
    other = User(telegram_id=2, display_name="o", timezone="UTC")
    other.id = 99
    with pytest.raises(LookupError):
        await svc.end(dto.id, other, ended_at=T0 + timedelta(hours=1), peak_intensity=5)
