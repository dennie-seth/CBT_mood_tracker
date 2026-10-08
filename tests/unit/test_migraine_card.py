"""Attack card: the single message that shows an attack and edits it.

Pure rendering: (EntryDTO, lang, tz, now) -> (text, keyboard). Buttons carry
`mg:<action>:<entry_id>[:<arg>]` so they work without FSM state, and the
server re-checks ownership on every tap.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.bot.migraine_card import fmt_duration, render_card, summary_line
from app.domain.enums import MetricType
from app.services.entry_service import EntryDTO

NOW = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)


def _attack(**extra) -> EntryDTO:
    base = {
        "status": "ongoing",
        "started_at": (NOW - timedelta(hours=2, minutes=5)).isoformat(),
        "start_intensity": 6,
        "peak_intensity": 6,
        "aura": None,
        "symptoms": [],
        "triggers": [],
    }
    base.update(extra)
    return EntryDTO(
        id=7, recorded_at=datetime.fromisoformat(base["started_at"]),
        entry_date=date(2026, 10, 8), metric_type=MetricType.MIGRAINE,
        value_numeric=float(max(base["start_intensity"], base["peak_intensity"])),
        value_text=None, tags=None, extra=base,
    )


def _buttons(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_open_card_text() -> None:
    text, _ = render_card(_attack(), "en", "UTC", NOW)
    assert "ongoing" in text
    assert "15:55" in text and "2h 5m ago" in text
    assert "6/10" in text
    assert "Aura: —" in text  # unanswered is shown as unknown, not "no"


def test_open_card_buttons() -> None:
    _, kb = render_card(_attack(), "en", "UTC", NOW)
    data = _buttons(kb)
    assert "mg:over:7" in data
    assert "mg:start:7" in data
    assert "mg:worse:7" in data
    assert "mg:del:7" in data
    assert "mg:relief:7" not in data  # no medication yet
    assert "mg:endtime:7" not in data
    assert all(len(d.encode()) <= 64 for d in data)


def test_relief_button_appears_with_medication() -> None:
    _, kb = render_card(_attack(medication_text="ibuprofen"), "en", "UTC", NOW)
    assert "mg:relief:7" in _buttons(kb)


def test_details_rendered() -> None:
    text, _ = render_card(
        _attack(
            aura=True, symptoms=["nausea", "light"], triggers=["sleep"],
            trigger_text="long call", medication_text="ibuprofen 400", relief=6,
            peak_intensity=8,
        ),
        "en", "UTC", NOW,
    )
    assert "Aura: yes" in text
    assert "Nausea" in text and "Light sensitivity" in text
    assert "Poor sleep" in text and "long call" in text
    assert "ibuprofen 400" in text and "helped 6/10" in text
    assert "worst 8/10" in text


def test_ended_card() -> None:
    started = NOW - timedelta(days=1, hours=3)
    text, kb = render_card(
        _attack(
            status="ended", started_at=started.isoformat(),
            ended_at=(started + timedelta(hours=27)).isoformat(),
            duration_minutes=27 * 60,
        ),
        "en", "UTC", NOW,
    )
    assert "ended" in text.lower()
    assert "yesterday 15:00" in text
    assert "1d 3h" in text
    data = _buttons(kb)
    assert "mg:over:7" not in data
    assert "mg:endtime:7" in data


def test_ended_unknown_card() -> None:
    text, _ = render_card(_attack(status="ended", end_unknown=True), "en", "UTC", NOW)
    assert "not recorded" in text


def test_stale_open_card_offers_forgot_end() -> None:
    a = _attack(started_at=(NOW - timedelta(hours=80)).isoformat())
    text, kb = render_card(a, "en", "UTC", NOW)
    assert "forget" in text.lower()
    assert "mg:forgot:7" in _buttons(kb)


def test_russian_card() -> None:
    text, _ = render_card(_attack(aura=False), "ru", "UTC", NOW)
    assert "Аура: нет" in text
    assert "назад" in text


@pytest.mark.parametrize(
    "minutes,en,ru",
    [(5, "5m", "5 мин"), (125, "2h 5m", "2 ч 5 мин"), (27 * 60, "1d 3h", "1 д 3 ч")],
)
def test_fmt_duration(minutes, en, ru) -> None:
    assert fmt_duration(minutes, "en") == en
    assert fmt_duration(minutes, "ru") == ru


def test_summary_line_is_compact() -> None:
    a = _attack(
        status="ended",
        ended_at=NOW.isoformat(), duration_minutes=125, peak_intensity=7,
        medication_text="ibuprofen", relief=6,
    )
    line = summary_line(a, "en", "UTC", NOW)
    assert "15:55–18:00" in line and "2h 5m" in line and "peak 7" in line
    assert "ibuprofen" in line and "6/10" in line
