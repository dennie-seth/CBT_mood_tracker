from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
import pytz
from cryptography.fernet import Fernet

from app.domain.enums import MetricType
from app.domain.models import Entry, User
from app.infrastructure.crypto import FernetCipher
from app.services.entry_service import EntryService


class FakeEntryRepo:
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

    async def daily_aggregates(self, user_id, start, end):
        return []


@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest.fixture()
def user() -> User:
    u = User(telegram_id=1, display_name="t", timezone="Europe/Berlin")
    u.id = 42
    return u


async def test_creates_numeric_entry(cipher, user) -> None:
    repo = FakeEntryRepo()
    svc = EntryService(repo, cipher)
    dto = await svc.create(user, MetricType.MOOD, value_numeric=7)
    assert dto.value_numeric == 7.0
    assert dto.value_text is None
    assert repo.rows[0].value_numeric == Decimal("7")
    assert repo.rows[0].value_text_encrypted is None


async def test_creates_text_entry_encrypted(cipher, user) -> None:
    repo = FakeEntryRepo()
    svc = EntryService(repo, cipher)
    dto = await svc.create(user, MetricType.NOTE, value_text="secret")
    # Ciphertext must not be human-readable
    raw = repo.rows[0].value_text_encrypted
    assert raw is not None and b"secret" not in raw
    # DTO decrypts back
    assert dto.value_text == "secret"


async def test_metadata_text_fields_encrypted(cipher, user) -> None:
    repo = FakeEntryRepo()
    svc = EntryService(repo, cipher)
    extra = {
        "situation_text": "elevator small talk",
        "automatic_thought_text": "they think I'm boring",
        "distortion_text": "mind-reading",
        "reframe_text": "I have no evidence of that",
    }
    dto = await svc.create(user, MetricType.THOUGHT_RECORD, extra=extra)

    raw_extra = repo.rows[0].extra
    assert raw_extra is not None
    for k in extra:
        # Stored as wrapped dict, NOT plaintext
        assert isinstance(raw_extra[k], dict) and raw_extra[k].get("__enc__") is True
    # DTO restores plaintext
    assert dto.extra == extra


async def test_day_bucketing_respects_user_timezone(cipher) -> None:
    user = User(telegram_id=1, display_name="t", timezone="Pacific/Auckland")
    user.id = 1
    repo = FakeEntryRepo()
    svc = EntryService(repo, cipher)
    # 2026-05-04 23:00 UTC == 2026-05-05 11:00 in Auckland (NZST is UTC+12).
    ts = pytz.utc.localize(datetime(2026, 5, 4, 23, 0))
    dto = await svc.create(user, MetricType.MOOD, value_numeric=5, recorded_at=ts)
    assert dto.entry_date == date(2026, 5, 5)


async def test_validates_required_fields(cipher, user) -> None:
    svc = EntryService(FakeEntryRepo(), cipher)
    with pytest.raises(ValueError):
        await svc.create(user, MetricType.MOOD)  # numeric metric, missing value
    with pytest.raises(ValueError):
        await svc.create(user, MetricType.NOTE)  # text metric, missing content
