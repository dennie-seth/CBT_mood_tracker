"""Service pieces behind /recent and the behavioral-activation wording fix."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.bot.i18n import EN, RU
from app.domain.enums import MetricType
from app.domain.models import User
from app.services.activation_service import ActivationService
from app.services.entry_service import MAX_TEXT_BYTES, EntryService
from tests.unit.fakes import FakeEntryRepo


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


# --- EntryService.update_value (edit from /recent) ------------------------

async def test_update_numeric_value(es, user) -> None:
    e = await es.create(user, MetricType.MOOD, value_numeric=3)
    dto = await es.update_value(e.id, user, value_numeric=6)
    assert dto.value_numeric == 6.0


async def test_update_text_value_reencrypts(es, repo, user) -> None:
    e = await es.create(user, MetricType.NOTE, value_text="typo hree")
    dto = await es.update_value(e.id, user, value_text="typo here")
    assert dto.value_text == "typo here"
    assert b"typo" not in repo.rows[0].value_text_encrypted


async def test_update_value_kind_must_match_metric(es, user) -> None:
    mood = await es.create(user, MetricType.MOOD, value_numeric=3)
    note = await es.create(user, MetricType.NOTE, value_text="x")
    with pytest.raises(ValueError):
        await es.update_value(mood.id, user, value_text="nope")
    with pytest.raises(ValueError):
        await es.update_value(note.id, user, value_numeric=5)


async def test_update_value_caps_text_and_checks_owner(es, user, other) -> None:
    note = await es.create(user, MetricType.NOTE, value_text="x")
    with pytest.raises(ValueError):
        await es.update_value(note.id, user, value_text="x" * (MAX_TEXT_BYTES + 1))
    with pytest.raises(PermissionError):
        await es.update_value(note.id, other, value_text="hijack")


# --- activation: prediction calibration -------------------------------------

async def _done_plan(es, user, when: date, text: str, predicted: int, actual: int) -> None:
    await es.create(
        user, MetricType.ACTIVITY_PLAN, recorded_at=datetime(when.year, when.month, when.day, 12, tzinfo=UTC),
        extra={"plan_text": text, "planned_for": when.isoformat(), "predicted_effect": predicted,
               "status": "done", "actual_effect": actual},
    )


TODAY = date(2026, 10, 8)


async def test_calibration_needs_enough_history(es, user) -> None:
    await _done_plan(es, user, TODAY - timedelta(days=3), "walk", 3, 7)
    await _done_plan(es, user, TODAY - timedelta(days=2), "call mum", 4, 7)
    assert await ActivationService(es).calibration(user.id, today=TODAY, plan_text="read") is None


async def test_calibration_overall(es, user) -> None:
    for i, (p, a) in enumerate([(3, 6), (4, 6), (5, 7)]):
        await _done_plan(es, user, TODAY - timedelta(days=i + 1), f"thing {i}", p, a)
    cal = await ActivationService(es).calibration(user.id, today=TODAY, plan_text="new thing")
    assert cal is not None
    assert cal.delta == pytest.approx(2.3, abs=0.05)
    assert cal.n == 3
    assert cal.specific is False


async def test_calibration_prefers_same_activity(es, user) -> None:
    await _done_plan(es, user, TODAY - timedelta(days=5), "Walk", 3, 8)
    await _done_plan(es, user, TODAY - timedelta(days=4), "walk ", 4, 8)
    await _done_plan(es, user, TODAY - timedelta(days=3), "tidy desk", 6, 5)
    cal = await ActivationService(es).calibration(user.id, today=TODAY, plan_text="walk")
    assert cal is not None and cal.specific is True
    assert cal.n == 2 and cal.delta == pytest.approx(4.5)


async def test_calibration_silent_when_predictions_are_accurate(es, user) -> None:
    for i in range(4):
        await _done_plan(es, user, TODAY - timedelta(days=i + 1), f"t{i}", 5, 5)
    assert await ActivationService(es).calibration(user.id, today=TODAY, plan_text="x") is None


# --- wording: a 1-10 "how much it helps" rating, not a "+N" delta ----------

@pytest.mark.parametrize("table", [EN, RU])
def test_activation_strings_rate_not_delta(table) -> None:
    keys = ["activate.ask_predicted", "activate.saved", "plans.predicted_suffix",
            "done.ask_actual", "done.saved_with_pred", "done.saved"]
    for k in keys:
        assert "+{" not in table[k], k
    assert "10" in table["activate.ask_predicted"]
    assert "10" in table["done.ask_actual"]
