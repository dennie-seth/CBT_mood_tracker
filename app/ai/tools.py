from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytz

from app.domain.enums import MetricType
from app.services.analysis_service import AnalysisService
from app.services.chart_service import ChartService
from app.services.entry_service import EntryService
from app.services.pdf_service import PdfService


def _safe_metric_types(types_raw: list[Any]) -> list[MetricType]:
    """Coerce strings to MetricType, silently dropping unknowns. Public API
    only — no reliance on `_value2member_map_`."""
    out: list[MetricType] = []
    for t in types_raw:
        try:
            out.append(MetricType(t))
        except ValueError:
            continue
    return out


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "query_entries",
        "description": (
            "Fetch the user's entries between two ISO dates (inclusive). "
            "Optionally filter by metric_types. Returns entries in chronological "
            "order, each with its local date and time (the user's timezone), "
            "numeric value, free-text value, tags and metadata. Use this — not "
            "daily_summary — when the order of events or the link between a note "
            "and a nearby metric matters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "metric_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of metric_type names to filter by.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional cap on number of rows returned (default 200, max 1000).",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "daily_summary",
        "description": (
            "Compute per-day averages of numeric metrics over a date range. "
            "Returns an array of {date, metrics: {metric_type: avg_value}}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "generate_chart",
        "description": (
            "Render a PNG chart of selected numeric metrics over a date range. "
            "Returns an artifact reference; the host will deliver the image to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "metric_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Numeric metric names to include.",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "generate_pdf_report",
        "description": (
            "Render a multi-page PDF report for a date range (cover, stats, per-metric charts, "
            "correlations). Returns an artifact reference; the host will deliver the document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["start_date", "end_date"],
        },
    },
]


@dataclass
class ToolArtifact:
    """A binary artifact produced by a tool, to be sent back to the user."""

    kind: str  # "image/png" | "application/pdf"
    filename: str
    data: bytes


@dataclass
class ToolDispatcher:
    """Executes Haiku tool calls with the user_id bound by the host (never by the model)."""

    user_id: int
    user_timezone: str
    entry_service: EntryService
    analysis_service: AnalysisService
    chart_service: ChartService
    pdf_service: PdfService
    artifacts: list[ToolArtifact] = field(default_factory=list)

    async def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "query_entries":
            return await self._query_entries(args)
        if name == "daily_summary":
            return await self._daily_summary(args)
        if name == "generate_chart":
            return await self._generate_chart(args)
        if name == "generate_pdf_report":
            return await self._generate_pdf_report(args)
        return {"error": f"Unknown tool: {name}"}

    async def _query_entries(self, args: dict[str, Any]) -> dict[str, Any]:
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"])
        types_raw = args.get("metric_types") or []
        limit = min(int(args.get("limit", 200)), 1000)
        metric_types = _safe_metric_types(types_raw)
        rows = await self.entry_service.list_range(
            self.user_id, start, end, metric_types or None
        )
        rows = rows[:limit]
        tz = pytz.timezone(self.user_timezone)
        entries = []
        for r in rows:
            local = r.recorded_at.astimezone(tz)
            entries.append(
                {
                    "date": r.entry_date.isoformat(),
                    "time": local.strftime("%H:%M"),
                    "recorded_at": local.isoformat(),
                    "metric_type": r.metric_type.value,
                    "value_numeric": (
                        float(r.value_numeric) if r.value_numeric is not None else None
                    ),
                    "value_text": r.value_text,
                    "tags": r.tags,
                    "extra": r.extra,
                }
            )
        return {"count": len(entries), "entries": entries}

    async def _daily_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"])
        df = await self.analysis_service.daily_summary(self.user_id, start, end)
        if df.empty:
            return {"days": [], "note": "No data in range."}
        return {
            "days": [
                {
                    "date": idx.date().isoformat(),
                    "metrics": {
                        c: (None if (v := row[c]) is None or _is_nan(v) else float(v))
                        for c in df.columns
                    },
                }
                for idx, row in df.iterrows()
            ]
        }

    async def _generate_chart(self, args: dict[str, Any]) -> dict[str, Any]:
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"])
        types_raw = args.get("metric_types") or []
        metrics = _safe_metric_types(types_raw)
        df = await self.analysis_service.daily_summary(self.user_id, start, end)
        png = self.chart_service.line(df, metrics or None)
        fname = f"chart_{start.isoformat()}_{end.isoformat()}.png"
        self.artifacts.append(ToolArtifact("image/png", fname, png))
        return {"artifact": fname, "ok": True}

    async def _generate_pdf_report(self, args: dict[str, Any]) -> dict[str, Any]:
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"])
        title = args.get("title") or "CBT tracker report"
        df = await self.analysis_service.daily_summary(self.user_id, start, end)
        pdf = self.pdf_service.report(df, start=start, end=end, title=title)
        fname = f"report_{start.isoformat()}_{end.isoformat()}.pdf"
        self.artifacts.append(ToolArtifact("application/pdf", fname, pdf))
        return {"artifact": fname, "ok": True}


def _is_nan(v: object) -> bool:
    try:
        return v != v  # NaN is the only value not equal to itself
    except Exception:
        return False
