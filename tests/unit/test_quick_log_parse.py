"""parse_quick_log: 'mood 6 anxiety 7 slept 6.5' → several entries at once.

Local parsing only (no AI). A message is a quick log only if the WHOLE text
is metric/value pairs — "mood was 5 because…" must stay a note.
"""
from __future__ import annotations

import pytest

from app.domain.enums import MetricType
from app.services.quick_log import parse_quick_log

M = MetricType


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mood 6", [(M.MOOD, 6.0)]),
        ("Mood 6 anxiety 7", [(M.MOOD, 6.0), (M.ANXIETY, 7.0)]),
        ("mood 6, anxiety 7; stress 3", [(M.MOOD, 6.0), (M.ANXIETY, 7.0), (M.STRESS, 3.0)]),
        ("mood: 6", [(M.MOOD, 6.0)]),
        ("mood=6 energy=4", [(M.MOOD, 6.0), (M.ENERGY, 4.0)]),
        ("slept 6.5", [(M.SLEEP_HOURS, 6.5)]),
        ("slept 7,5", [(M.SLEEP_HOURS, 7.5)]),
        ("sleep 7", [(M.SLEEP_QUALITY, 7.0)]),
        ("sleep 7h", [(M.SLEEP_HOURS, 7.0)]),
        ("настроение 4 тревога 8", [(M.MOOD, 4.0), (M.ANXIETY, 8.0)]),
        ("сон 7ч", [(M.SLEEP_HOURS, 7.0)]),
        ("спала 6,5", [(M.SLEEP_HOURS, 6.5)]),
        ("Энергия 3, боль 2", [(M.ENERGY, 3.0), (M.PAIN, 2.0)]),
        ("pain 0", [(M.PAIN, 0.0)]),
    ],
)
def test_parses(raw, expected) -> None:
    assert parse_quick_log(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "hello",
        "mood was 5 because of the call",
        "mood 6 and then I went out",
        "mood",
        "6",
        "mood 11",  # out of scale
        "slept 25",
        "mood 6 mood 7",  # duplicate metric is ambiguous
        "migraine 6",  # migraines go through the attack card
    ],
)
def test_rejects(raw) -> None:
    assert parse_quick_log(raw) is None
