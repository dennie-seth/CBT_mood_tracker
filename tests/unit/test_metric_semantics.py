from __future__ import annotations

from app.domain.enums import (
    METRIC_LABELS,
    METRIC_SEMANTICS,
    NUMERIC_METRICS,
    MetricType,
    metric_semantics_block,
)


def test_every_numeric_metric_has_semantics() -> None:
    for m in NUMERIC_METRICS:
        assert m in METRIC_SEMANTICS, f"missing semantics for {m}"
        assert METRIC_SEMANTICS[m].strip()


def test_polarity_is_explicit() -> None:
    assert "Higher is better" in METRIC_SEMANTICS[MetricType.MOOD]
    assert "Higher is better" in METRIC_SEMANTICS[MetricType.ENERGY]
    assert "Higher is better" in METRIC_SEMANTICS[MetricType.FOCUS]
    assert "Higher is worse" in METRIC_SEMANTICS[MetricType.ANXIETY]
    assert "Higher is worse" in METRIC_SEMANTICS[MetricType.STRESS]
    assert "Higher is worse" in METRIC_SEMANTICS[MetricType.PAIN]


def test_semantics_block_lists_all_numeric_metrics() -> None:
    block = metric_semantics_block()
    for m in NUMERIC_METRICS:
        assert METRIC_LABELS[m] in block
    # Stable ordering follows the enum definition (mood before anxiety).
    assert block.index(METRIC_LABELS[MetricType.MOOD]) < block.index(
        METRIC_LABELS[MetricType.ANXIETY]
    )
