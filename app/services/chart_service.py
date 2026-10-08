from __future__ import annotations

import calendar
import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from app.domain.enums import METRIC_LABELS, MetricType  # noqa: E402

# Reference diverging pair (red <-> blue, neutral gray midpoint) and light
# chart surface from the dataviz palette; text stays in ink tokens.
_LOW, _MID, _HIGH = "#e34948", "#f0efec", "#2a78d6"
_SURFACE = "#fcfcfb"
_EMPTY_EDGE = "#d6d4ce"
_INK = "#2b2b29"
_MUTED = "#6b6a66"


class ChartService:
    """Renders matplotlib figures into PNG bytes."""

    def line(self, df: pd.DataFrame, metrics: list[MetricType] | None = None) -> bytes:
        if df.empty or df.shape[1] == 0:
            return self._placeholder("No data to chart for this period.")

        if metrics:
            requested = [m.value for m in metrics]
            cols = [c for c in requested if c in df.columns]
            # Best-effort fallback: if NONE of the requested metrics are in the
            # data (e.g. AI asked for mood/energy/anxiety but the user only
            # logged sleep this week), render whatever data IS there instead
            # of a useless "no matching metrics" image.
            if not cols:
                cols = list(df.columns)
        else:
            cols = list(df.columns)

        fig, ax = plt.subplots(figsize=(10, 5))
        for c in cols:
            label = METRIC_LABELS.get(MetricType(c), c)
            if c == MetricType.MIGRAINE.value:
                # Episodic: days without an attack are gaps, not missing data,
                # so mark attack days instead of joining them with a line.
                ax.scatter(df.index, df[c], marker="v", s=70, zorder=3, label=label)
            else:
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

    def year_pixels(
        self, df: pd.DataFrame, *, year: int, today: date | None = None
    ) -> bytes:
        """Year in pixels: one cell per day (rows = months), coloured by the
        day's mood on a diverging red (low) - gray (5) - blue (good) scale;
        days without a mood entry stay empty-outlined so they never read as
        a neutral 5; a ▼ marks migraine days (glyph, not colour alone).
        Days after `today` are left blank. Labels stay English like the
        other charts."""
        has_mood = not df.empty and "mood" in df.columns and df["mood"].notna().any()
        has_migraine = not df.empty and "migraine" in df.columns and df["migraine"].notna().any()
        if not (has_mood or has_migraine):
            return self._placeholder(f"Nothing logged in {year} yet.")

        mood = df["mood"].dropna() if has_mood else pd.Series(dtype=float)
        attacks = set(df["migraine"].dropna().index.date) if has_migraine else set()
        mood_by_day = {ts.date(): float(v) for ts, v in mood.items()}

        cmap = LinearSegmentedColormap.from_list(
            "mood", [(0.0, _LOW), (4 / 9, _MID), (1.0, _HIGH)]
        )
        norm = Normalize(vmin=1, vmax=10)

        fig, ax = plt.subplots(figsize=(12, 5.4))
        fig.patch.set_facecolor(_SURFACE)
        ax.set_facecolor(_SURFACE)
        for month in range(1, 13):
            row = 12 - month  # January on top
            for day in range(1, calendar.monthrange(year, month)[1] + 1):
                d = date(year, month, day)
                if today is not None and d > today:
                    continue
                x = day - 1
                if d in mood_by_day:
                    ax.add_patch(Rectangle(
                        (x + 0.06, row + 0.06), 0.88, 0.88, linewidth=0,
                        facecolor=cmap(norm(mood_by_day[d])),
                    ))
                else:
                    ax.add_patch(Rectangle(
                        (x + 0.1, row + 0.1), 0.8, 0.8, linewidth=0.6,
                        edgecolor=_EMPTY_EDGE, facecolor=_SURFACE,
                    ))
                if d in attacks:
                    ax.text(x + 0.5, row + 0.48, "▼", ha="center", va="center",
                            fontsize=7, color=_INK)

        ax.set_xlim(0, 31)
        ax.set_ylim(0, 12)
        ax.set_xticks([d - 0.5 for d in (1, 5, 10, 15, 20, 25, 31)])
        ax.set_xticklabels(["1", "5", "10", "15", "20", "25", "31"], color=_MUTED, fontsize=8)
        ax.set_yticks([11.5 - i for i in range(12)])
        ax.set_yticklabels(list(calendar.month_abbr)[1:], color=_INK, fontsize=9)
        ax.tick_params(length=0)
        ax.spines[:].set_visible(False)
        ax.set_aspect("equal")
        ax.set_title(f"Mood {year}", loc="left", fontsize=14, color=_INK)

        bar = fig.colorbar(
            ScalarMappable(norm=norm, cmap=cmap), ax=ax, orientation="horizontal",
            fraction=0.04, pad=0.08, aspect=40, ticks=[1, 5, 10],
        )
        bar.ax.set_xticklabels(["1 low", "5 neutral", "10 good"], color=_MUTED, fontsize=8)
        bar.outline.set_visible(False)
        ax.text(31, 12.25, "▼ migraine day    □ no mood logged", ha="right", va="bottom",
                fontsize=8, color=_MUTED)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, facecolor=_SURFACE)
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
