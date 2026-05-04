from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from app.domain.enums import METRIC_LABELS, MetricType  # noqa: E402


class PdfService:
    """Composes a multi-page PDF report from a daily summary DataFrame."""

    def report(
        self,
        df: pd.DataFrame,
        *,
        start: date,
        end: date,
        title: str = "CBT tracker report",
    ) -> bytes:
        buf = io.BytesIO()
        with PdfPages(buf) as pdf:
            self._cover_page(pdf, title=title, start=start, end=end, df=df)
            if not df.empty:
                self._stats_page(pdf, df)
                for col in df.columns:
                    self._metric_page(pdf, df, col)
                if df.shape[1] >= 2:
                    self._correlation_page(pdf, df)
        return buf.getvalue()

    def _cover_page(
        self, pdf: PdfPages, *, title: str, start: date, end: date, df: pd.DataFrame
    ) -> None:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4
        ax.axis("off")
        ax.text(0.5, 0.85, title, ha="center", fontsize=22, weight="bold")
        ax.text(
            0.5, 0.78, f"{start.isoformat()} → {end.isoformat()}",
            ha="center", fontsize=14
        )
        days = (end - start).days + 1
        n_metrics = df.shape[1] if not df.empty else 0
        n_days = df.shape[0] if not df.empty else 0
        body = (
            f"Range: {days} day(s)\n"
            f"Metrics with data: {n_metrics}\n"
            f"Days with data: {n_days}\n"
        )
        ax.text(0.1, 0.55, body, fontsize=12, family="monospace")
        pdf.savefig(fig)
        plt.close(fig)

    def _stats_page(self, pdf: PdfPages, df: pd.DataFrame) -> None:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis("off")
        ax.set_title("Summary statistics", fontsize=16, loc="left")
        stats = df.describe().round(2)
        rows = [["metric"] + list(stats.index)]
        for col in stats.columns:
            rows.append([METRIC_LABELS.get(MetricType(col), col)] + [
                str(v) for v in stats[col].tolist()
            ])
        table = ax.table(cellText=rows, loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.4)
        pdf.savefig(fig)
        plt.close(fig)

    def _metric_page(self, pdf: PdfPages, df: pd.DataFrame, col: str) -> None:
        fig, ax = plt.subplots(figsize=(8.27, 5.5))
        label = METRIC_LABELS.get(MetricType(col), col) if col in MetricType.__members__.values() else col
        ax.plot(df.index, df[col], marker="o", linewidth=1.5)
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    def _correlation_page(self, pdf: PdfPages, df: pd.DataFrame) -> None:
        corr = df.corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(8.27, 8.27))
        im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(corr.columns, fontsize=8)
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                ax.text(
                    j, i, f"{corr.values[i, j]:.2f}",
                    ha="center", va="center", fontsize=7,
                )
        ax.set_title("Correlation between metrics")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
