from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from app.domain.enums import METRIC_LABELS, MetricType  # noqa: E402


class ChartService:
    """Renders matplotlib figures into PNG bytes."""

    def line(self, df: pd.DataFrame, metrics: list[MetricType] | None = None) -> bytes:
        if df.empty:
            return self._placeholder("No data to chart for this period.")

        cols = [m.value for m in metrics] if metrics else list(df.columns)
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return self._placeholder("No matching metrics for this period.")

        fig, ax = plt.subplots(figsize=(10, 5))
        for c in cols:
            label = METRIC_LABELS.get(MetricType(c), c)
            ax.plot(df.index, df[c], marker="o", linewidth=1.5, label=label)

        ax.set_title("CBT tracker — daily averages")
        ax.set_ylabel("value")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()

    def _placeholder(self, msg: str) -> bytes:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=14)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        return buf.getvalue()
