"""All of the user's own entries as CSV — decrypted, for keeping or moving.

UTF-8 with BOM so Excel opens Cyrillic correctly; times in the user's tz;
`details` is the entry's metadata as JSON (free-text fields decrypted).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date

import pytz

from app.domain.models import User
from app.services.entry_service import EntryService

HEADER = ["date", "time", "metric", "value", "text", "details"]


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


class CsvExportService:
    def __init__(self, entries: EntryService) -> None:
        self._entries = entries

    async def export(self, user: User, start: date, end: date) -> bytes:
        rows = await self._entries.list_range(user.id, start, end)
        tz = pytz.timezone(user.timezone)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(HEADER)
        for e in sorted(rows, key=lambda e: (e.recorded_at, e.id)):
            local = e.recorded_at.astimezone(tz)
            writer.writerow([
                e.entry_date.isoformat(),
                local.strftime("%H:%M"),
                e.metric_type.value,
                _fmt(e.value_numeric) if e.value_numeric is not None else "",
                e.value_text or "",
                json.dumps(e.extra, ensure_ascii=False) if e.extra else "",
            ])
        return buf.getvalue().encode("utf-8-sig")
