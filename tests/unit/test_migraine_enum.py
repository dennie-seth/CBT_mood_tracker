"""MIGRAINE is a NUMERIC metric: value_numeric = peak intensity 1-10.

Numeric so charts / PDF / daily_summary / AI scale semantics pick it up
for free. Episode details live in `extra` (see MigraineService).
"""
from __future__ import annotations

from app.bot.i18n import metric_label
from app.domain.enums import (
    METRIC_LABELS,
    METRIC_SEMANTICS,
    NUMERIC_METRICS,
    TEXT_METRICS,
    MetricType,
)


def test_migraine_value() -> None:
    assert MetricType.MIGRAINE.value == "migraine"


def test_migraine_is_numeric() -> None:
    assert MetricType.MIGRAINE in NUMERIC_METRICS
    assert MetricType.MIGRAINE not in TEXT_METRICS


def test_migraine_has_labels_in_both_languages() -> None:
    assert METRIC_LABELS[MetricType.MIGRAINE]
    assert metric_label(MetricType.MIGRAINE, "ru") != METRIC_LABELS[MetricType.MIGRAINE]


def test_migraine_semantics_explain_polarity_and_absence() -> None:
    s = METRIC_SEMANTICS[MetricType.MIGRAINE]
    assert "Higher is worse" in s
    # A day without an entry is "no attack logged", not a zero reading.
    assert "no attack" in s.lower()
