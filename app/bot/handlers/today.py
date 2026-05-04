from __future__ import annotations

from datetime import timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.domain.enums import METRIC_LABELS, NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.time import today_in_tz

router = Router()


def _format_entries(entries: list, header: str) -> str:
    if not entries:
        return f"{header}\n(no entries)"

    by_metric: dict[MetricType, list] = {}
    for e in entries:
        by_metric.setdefault(e.metric_type, []).append(e)

    lines = [header]
    for metric, items in sorted(by_metric.items(), key=lambda kv: kv[0].value):
        label = METRIC_LABELS[metric]
        if metric in NUMERIC_METRICS:
            vals = [i.value_numeric for i in items if i.value_numeric is not None]
            avg = sum(vals) / len(vals) if vals else None
            avg_str = f" (avg {avg:.1f})" if avg is not None and len(vals) > 1 else ""
            joined = ", ".join(f"{v}" for v in vals)
            lines.append(f"• {label}: {joined}{avg_str}")
        else:
            for it in items:
                snippet = (it.value_text or "").strip().replace("\n", " ")
                if not snippet and it.extra:
                    parts = [f"{k}={v}" for k, v in it.extra.items() if isinstance(v, str)]
                    snippet = " | ".join(parts)
                if len(snippet) > 120:
                    snippet = snippet[:117] + "…"
                lines.append(f"• {label}: {snippet or '(empty)'}")
    return "\n".join(lines)


@router.message(Command("today"))
async def cmd_today(
    message: Message,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    today = today_in_tz(user.timezone)
    svc = entry_service(session, cipher)
    entries = await svc.list_range(user.id, today, today)
    await message.answer(_format_entries(entries, f"Today {today.isoformat()}:"))


@router.message(Command("week"))
async def cmd_week(
    message: Message,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    today = today_in_tz(user.timezone)
    start = today - timedelta(days=6)
    svc = entry_service(session, cipher)
    entries = await svc.list_range(user.id, start, today)
    await message.answer(
        _format_entries(entries, f"Last 7 days ({start.isoformat()} → {today.isoformat()}):")
    )
