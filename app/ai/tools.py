from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytz

from app.domain.enums import MetricType
from app.services.analysis_service import AnalysisService
from app.services.chart_service import ChartService
from app.services.entry_service import EntryService
from app.services.migraine_stats import MigraineStats, compute_stats
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
            "Returns days: [{date, weekday, metrics: {metric_type: avg_value}}] and "
            "days_without_data: [{date, weekday}] for days in the range with no "
            "numeric entry (nothing logged — not a zero)."
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
        "name": "migraine_stats",
        "description": (
            "Exact migraine summary for a date range: number of attacks, "
            "headache days, typical and longest duration (over "
            "attacks_with_known_duration only — attacks with no recorded end have "
            "no duration), average/max peak, "
            "aura count, symptom and trigger counts (most common first), "
            "medications with how often each was used and average relief, and "
            "medication_days_last_30 (days with acute medication logged in the "
            "30 days up to today). Use this for any counting or frequency "
            "question instead of counting raw entries yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
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
        if name == "migraine_stats":
            return await self._migraine_stats(args)
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
                    "weekday": _weekday(local.date()),
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
        logged = set() if df.empty else {idx.date() for idx in df.index}
        missing = _days_without_data(start, end, logged)
        if df.empty:
            return {"days": [], "note": "No data in range.", **missing}
        return {
            **missing,
            "days": [
                {
                    "date": idx.date().isoformat(),
                    "weekday": _weekday(idx.date()),
                    "metrics": {
                        c: (None if (v := row[c]) is None or _is_nan(v) else float(v))
                        for c in df.columns
                    },
                }
                for idx, row in df.iterrows()
            ]
        }

    async def _migraine_stats(self, args: dict[str, Any]) -> dict[str, Any]:
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"])
        now = datetime.now(tz=UTC)
        today = now.astimezone(pytz.timezone(self.user_timezone)).date()
        out = (await self._migraine_stats_for(start, end, now)).to_dict()
        last30 = await self._migraine_stats_for(today - timedelta(days=29), today, now)
        out["medication_days_last_30"] = last30.medication_days
        return out

    async def _migraine_stats_for(self, start: date, end: date, now: datetime) -> MigraineStats:
        rows = await self.entry_service.list_range(
            self.user_id, start, end, [MetricType.MIGRAINE]
        )
        rows = [r for r in rows if r.metric_type == MetricType.MIGRAINE]
        return compute_stats(rows, start=start, end=end, tz_name=self.user_timezone, now=now)

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


_MAX_LISTED_EMPTY_DAYS = 92


def _days_without_data(start: date, end: date, logged: set[date]) -> dict[str, Any]:
    """Empty days with their weekday, so the model never has to compute one.
    Long ranges get a count instead of a list."""
    span = (end - start).days + 1
    empty = [start + timedelta(days=i) for i in range(max(span, 0))
             if start + timedelta(days=i) not in logged]
    if span > _MAX_LISTED_EMPTY_DAYS:
        return {"days_without_data_count": len(empty)}
    return {"days_without_data": [{"date": d.isoformat(), "weekday": _weekday(d)} for d in empty]}


_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _weekday(d: date) -> str:
    """Locale-independent short weekday, so the model never has to compute
    one from an ISO date (a common source of "on Tuesday" mistakes)."""
    return _WEEKDAYS[d.weekday()]


def _is_nan(v: object) -> bool:
    try:
        return v != v  # NaN is the only value not equal to itself
    except Exception:
        return False
