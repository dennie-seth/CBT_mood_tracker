"""Chart service tests, with focus on the requested-vs-available metric fallback.

Regression: the WEEKLY_PROMPT asks Haiku to chart mood + energy + anxiety.
If the user logged none of those that week, the original implementation
returned a "No matching metrics" placeholder image instead of charting
whatever data they DID log. We prefer a best-effort chart over a useless one.
"""
from __future__ import annotations

import pandas as pd

from app.domain.enums import MetricType
from app.services.chart_service import ChartService


def _df(**cols: list[float]) -> pd.DataFrame:
    idx = pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-03"])
    return pd.DataFrame(cols, index=idx)


def _placeholder_size() -> int:
    """Size of the 'no data' placeholder, used as a baseline to detect real charts."""
    return len(ChartService().line(pd.DataFrame()))


def test_empty_df_returns_placeholder() -> None:
    png = ChartService().line(pd.DataFrame())
    assert png.startswith(b"\x89PNG")


def test_renders_real_chart_when_metrics_match() -> None:
    df = _df(mood=[5.0, 6.0, 7.0], energy=[4.0, 5.0, 6.0])
    png = ChartService().line(df, [MetricType.MOOD, MetricType.ENERGY])
    # A real two-series chart is materially larger than the placeholder.
    assert len(png) > _placeholder_size() * 1.5


def test_partial_match_renders_present_subset() -> None:
    """Some requested metrics exist, some don't — render the present ones."""
    df = _df(mood=[5.0, 6.0, 7.0], sleep_hours=[7.0, 7.5, 8.0])
    png = ChartService().line(df, [MetricType.MOOD, MetricType.ANXIETY])
    # mood is present → real chart, not placeholder.
    assert len(png) > _placeholder_size() * 1.5


def test_zero_overlap_falls_back_to_render_all_present_metrics() -> None:
    """Headline regression: AI asks for [mood, energy, anxiety] but the user only
    logged sleep_quality this week. Don't return a useless placeholder — chart
    what's actually there."""
    df = _df(sleep_quality=[6.0, 7.0, 8.0])
    chart = ChartService()
    fallback = chart.line(df, [MetricType.MOOD, MetricType.ENERGY, MetricType.ANXIETY])
    natural = chart.line(df)  # what we'd render with no filter

    # Both must be real charts (not the placeholder).
    assert len(fallback) > _placeholder_size() * 1.5
    assert len(natural) > _placeholder_size() * 1.5
    # And the fallback should look like the natural render (within charting jitter).
    assert abs(len(fallback) - len(natural)) < len(natural) * 0.2  # within 20%
