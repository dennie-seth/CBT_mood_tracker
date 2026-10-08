from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import metric_label, t
from app.bot.migraine_card import summary_line
from app.domain.enums import NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.time import today_in_tz

router = Router()


def _format_entries(
    entries: list,
    header: str,
    lang: str,
    empty_key: str,
    *,
    tz: str = "UTC",
    now: datetime | None = None,
) -> str:
    if not entries:
        return t(lang, empty_key)

    by_metric: dict[MetricType, list] = {}
    for e in entries:
        by_metric.setdefault(e.metric_type, []).append(e)

    lines = [header]
    for metric, items in sorted(by_metric.items(), key=lambda kv: kv[0].value):
        label = metric_label(metric, lang)
        if metric is MetricType.MIGRAINE:
            now = now or datetime.now(tz=UTC)
            for it in items:
                lines.append(t(
                    lang, "today.line_text", label=t(lang, "migraine.label"),
                    value=summary_line(it, lang, tz, now),
                ))
        elif metric in NUMERIC_METRICS:
            vals = [i.value_numeric for i in items if i.value_numeric is not None]
            avg = sum(vals) / len(vals) if vals else None
            avg_str = f" (avg {avg:.1f})" if avg is not None and len(vals) > 1 else ""
            joined = ", ".join(f"{v}" for v in vals)
            lines.append(
                t(lang, "today.line_numeric", label=label, value=f"{joined}{avg_str}")
            )
        else:
            for it in items:
                snippet = (it.value_text or "").strip().replace("\n", " ")
                if not snippet and it.extra:
                    parts = [
                        f"{k}={v}" for k, v in it.extra.items() if isinstance(v, str)
                    ]
                    snippet = " | ".join(parts)
                if len(snippet) > 120:
                    snippet = snippet[:117] + "…"
                lines.append(
                    t(lang, "today.line_text", label=label, value=snippet or "—")
                )
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
    header = f"{t(user.language, 'today.header')} {today.isoformat()}"
    await message.answer(
        _format_entries(entries, header, user.language, "today.empty", tz=user.timezone)
    )


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
    header = (
        f"{t(user.language, 'week.header')} "
        f"({start.isoformat()} → {today.isoformat()})"
    )
    await message.answer(
        _format_entries(entries, header, user.language, "week.empty", tz=user.timezone)
    )
