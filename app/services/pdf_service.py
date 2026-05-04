from __future__ import annotations

import io
import textwrap
from datetime import date
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from app.domain.enums import METRIC_LABELS, MetricType  # noqa: E402
from app.domain.models import User  # noqa: E402

if TYPE_CHECKING:
    from app.services.therapist_export_service import (
        BAOutcome,
        TextEntry,
        TherapistReportData,
        ThoughtRecord,
    )

# A4 in inches
_A4 = (8.27, 11.69)
# Wrap width (chars) for monospace 9pt body text on A4 with 1-inch margins.
_WRAP = 92
_FOOTER = "CONFIDENTIAL — for clinical review. Do not redistribute."


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

    # ------------------------------------------------------------------
    # Therapist report — richer, decrypted free-text included.

    def therapist_report(
        self,
        data: TherapistReportData,
        *,
        user: User,
        start: date,
        end: date,
    ) -> bytes:
        buf = io.BytesIO()
        with PdfPages(buf) as pdf:
            self._therapist_cover(pdf, user=user, start=start, end=end, data=data)
            df = data.daily_df
            if not df.empty:
                self._stats_page(pdf, df)
                for col in df.columns:
                    self._metric_page(pdf, df, col)
                if df.shape[1] >= 2:
                    self._correlation_page(pdf, df)
            if data.thought_records:
                self._thought_records_pages(pdf, data.thought_records)
            if data.ba_outcomes:
                self._ba_outcomes_page(pdf, data.ba_outcomes)
            if data.notes or data.other_text:
                self._free_text_pages(pdf, notes=data.notes, other=data.other_text)
        return buf.getvalue()

    def _therapist_cover(
        self,
        pdf: PdfPages,
        *,
        user: User,
        start: date,
        end: date,
        data: TherapistReportData,
    ) -> None:
        fig, ax = plt.subplots(figsize=_A4)
        ax.axis("off")
        ax.text(0.5, 0.88, "CBT tracker — therapist report",
                ha="center", fontsize=20, weight="bold")
        ax.text(0.5, 0.83, f"{start.isoformat()} → {end.isoformat()}",
                ha="center", fontsize=13)
        ax.text(0.5, 0.79, f"Patient: {user.display_name or '—'}    tz: {user.timezone}",
                ha="center", fontsize=11)

        days = (end - start).days + 1
        df = data.daily_df
        body = (
            f"Range:                 {days} day(s)\n"
            f"Days with numeric data: {df.shape[0] if not df.empty else 0}\n"
            f"Numeric metrics:        {df.shape[1] if not df.empty else 0}\n"
            f"Thought records:        {len(data.thought_records)}\n"
            f"Behavioral activation:  {len(data.ba_outcomes)}\n"
            f"Notes / other text:     {len(data.notes) + len(data.other_text)}\n"
        )
        ax.text(0.1, 0.55, body, fontsize=11, family="monospace")
        ax.text(
            0.5, 0.07, _FOOTER,
            ha="center", fontsize=9, style="italic", color="#444",
        )
        pdf.savefig(fig)
        plt.close(fig)

    def _new_text_page(self, title: str) -> tuple:
        fig, ax = plt.subplots(figsize=_A4)
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.05, 0.96, title, fontsize=14, weight="bold")
        ax.text(0.5, 0.02, _FOOTER, ha="center", fontsize=8,
                style="italic", color="#666")
        return fig, ax

    def _thought_records_pages(
        self, pdf: PdfPages, records: list[ThoughtRecord]
    ) -> None:
        fig, ax = self._new_text_page("Thought records")
        y = 0.92
        bottom = 0.06
        for rec in records:
            block_lines: list[tuple[str, str]] = [
                (f"{rec.entry_date.isoformat()}", ""),
                ("Situation:", rec.situation),
                ("Automatic thought:", rec.automatic_thought),
                ("Distortion:", rec.distortion),
                ("Reframe:", rec.reframe),
            ]
            wrapped: list[tuple[str, str]] = []
            for label, text in block_lines:
                if not text:
                    wrapped.append((label, ""))
                    continue
                lines = textwrap.wrap(text, width=_WRAP) or [""]
                wrapped.append((label, lines[0]))
                for cont in lines[1:]:
                    wrapped.append(("", cont))
            block_height = 0.025 * (len(wrapped) + 1)  # +1 spacer
            if y - block_height < bottom:
                pdf.savefig(fig)
                plt.close(fig)
                fig, ax = self._new_text_page("Thought records (cont.)")
                y = 0.92
            for label, text in wrapped:
                if label and not text:  # date header
                    ax.text(0.05, y, label, fontsize=10, weight="bold")
                elif label:
                    ax.text(0.05, y, label, fontsize=9, weight="bold")
                    ax.text(0.27, y, text, fontsize=9, family="monospace")
                else:
                    ax.text(0.27, y, text, fontsize=9, family="monospace")
                y -= 0.025
            y -= 0.015  # spacer between records
        pdf.savefig(fig)
        plt.close(fig)

    def _ba_outcomes_page(
        self, pdf: PdfPages, outcomes: list[BAOutcome]
    ) -> None:
        fig, ax = self._new_text_page("Behavioral activation — predicted vs. actual")
        rows: list[list[str]] = [["Date", "Plan", "Status", "Pred.", "Actual", "Reason"]]
        for o in outcomes:
            rows.append([
                o.entry_date.isoformat(),
                textwrap.shorten(o.plan_text, width=44, placeholder="…"),
                o.status,
                str(o.predicted_effect) if o.predicted_effect is not None else "—",
                str(o.actual_effect) if o.actual_effect is not None else "—",
                textwrap.shorten(o.skip_reason or "", width=24, placeholder="…") if o.skip_reason else "",
            ])
        table = ax.table(
            cellText=rows, loc="upper left", cellLoc="left",
            bbox=[0.05, 0.05, 0.9, 0.85],
            colWidths=[0.10, 0.34, 0.12, 0.08, 0.08, 0.18],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        # Bold the header row
        for j in range(len(rows[0])):
            table[0, j].set_text_props(weight="bold")
        pdf.savefig(fig)
        plt.close(fig)

    def _free_text_pages(
        self,
        pdf: PdfPages,
        *,
        notes: list[TextEntry],
        other: list[TextEntry],
    ) -> None:
        fig, ax = self._new_text_page("Notes & free-text entries")
        y = 0.92
        bottom = 0.06

        def render_section(title: str, entries: list[TextEntry]) -> None:
            nonlocal fig, ax, y
            if not entries:
                return
            if y - 0.04 < bottom:
                pdf.savefig(fig)
                plt.close(fig)
                fig, ax = self._new_text_page("Notes & free-text entries (cont.)")
                y = 0.92
            ax.text(0.05, y, title, fontsize=11, weight="bold")
            y -= 0.03
            for e in entries:
                lines = textwrap.wrap(e.text, width=_WRAP) or [""]
                block_h = 0.025 * (len(lines) + 1)
                if y - block_h < bottom:
                    pdf.savefig(fig)
                    plt.close(fig)
                    fig, ax = self._new_text_page(f"{title} (cont.)")
                    y = 0.92
                label = METRIC_LABELS.get(e.metric_type, e.metric_type.value)
                ax.text(
                    0.05, y,
                    f"{e.entry_date.isoformat()}  ·  {label}",
                    fontsize=9, weight="bold",
                )
                y -= 0.022
                for line in lines:
                    ax.text(0.07, y, line, fontsize=9, family="monospace")
                    y -= 0.022
                y -= 0.012

        render_section("Notes", notes)
        render_section("Other free-text", other)
        pdf.savefig(fig)
        plt.close(fig)
