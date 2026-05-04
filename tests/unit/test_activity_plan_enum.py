"""ACTIVITY_PLAN is a TEXT metric (because plan_text in extra is sensitive)."""
from __future__ import annotations

from app.domain.enums import (
    METRIC_LABELS,
    NUMERIC_METRICS,
    TEXT_METRICS,
    MetricType,
)


def test_activity_plan_value() -> None:
    assert MetricType.ACTIVITY_PLAN.value == "activity_plan"


def test_activity_plan_in_text_metrics_not_numeric() -> None:
    assert MetricType.ACTIVITY_PLAN in TEXT_METRICS
    assert MetricType.ACTIVITY_PLAN not in NUMERIC_METRICS


def test_activity_plan_has_label() -> None:
    label = METRIC_LABELS[MetricType.ACTIVITY_PLAN]
    assert label and isinstance(label, str)
