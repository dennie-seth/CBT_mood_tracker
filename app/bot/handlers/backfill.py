from __future__ import annotations

from datetime import datetime, time

import pytz
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.domain.enums import METRIC_LABELS, NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.time import parse_relative_date

router = Router()


def split_backfill_args(args: str) -> tuple[str, str, str]:
    """Split '/backfill <date> <metric> <value>' args.

    Returns (date_str, metric_type_str, rest). Recognises the 3-token
    'N day(s) ago' date phrase explicitly so it parses unambiguously.
    Raises ValueError on too few tokens.
    """
    tokens = args.split()
    if len(tokens) < 3:
        raise ValueError(
            "usage: /backfill <date> <metric> <value>\n"
            "examples: /backfill yesterday mood 7\n"
            "          /backfill 3 days ago note Felt rough."
        )
    if (
        len(tokens) >= 5
        and tokens[1].lower() in ("day", "days")
        and tokens[2].lower() == "ago"
    ):
        return " ".join(tokens[:3]), tokens[3], " ".join(tokens[4:])
    return tokens[0], tokens[1], " ".join(tokens[2:])


def _local_noon_utc(d, tz_name: str) -> datetime:
    """A timezone-aware UTC datetime corresponding to noon on `d` in the user's tz.

    Noon (instead of, say, 00:00) keeps `entry_date` stable under DST edges
    when EntryService converts back to user-local for bucketing.
    """
    tz = pytz.timezone(tz_name)
    return tz.localize(datetime.combine(d, time(12, 0))).astimezone(pytz.utc)


@router.message(Command("backfill"))
async def cmd_backfill(
    message: Message,
    command: CommandObject,
    user: User,
    session: AsyncSession,
    cipher: FernetCipher,
) -> None:
    if not command.args:
        await message.answer(
            "Usage: /backfill <date> <metric> <value>\n\n"
            "Date forms: today, yesterday, '3 days ago', or YYYY-MM-DD.\n"
            "Examples:\n"
            "  /backfill yesterday mood 7\n"
            "  /backfill 2026-05-04 sleep_hours 7.5\n"
            "  /backfill 3 days ago note Felt rough but the walk helped."
        )
        return

    try:
        date_str, metric_str, rest = split_backfill_args(command.args)
    except ValueError as e:
        await message.answer(str(e))
        return

    try:
        target_date = parse_relative_date(date_str, user.timezone)
    except ValueError as e:
        await message.answer(f"Date error: {e}")
        return

    try:
        metric = MetricType(metric_str)
    except ValueError:
        await message.answer(
            f"Unknown metric: {metric_str!r}. See /help for the metric list."
        )
        return

    svc = entry_service(session, cipher)
    recorded_at = _local_noon_utc(target_date, user.timezone)

    if metric in NUMERIC_METRICS:
        try:
            value = float(rest.replace(",", "."))
        except ValueError:
            await message.answer(
                f"{METRIC_LABELS[metric]} expects a number (e.g. 7 or 7.5)."
            )
            return
        try:
            dto = await svc.create(
                user, metric, value_numeric=value, recorded_at=recorded_at
            )
        except ValueError as e:
            await message.answer(str(e))
            return
    else:
        try:
            dto = await svc.create(
                user, metric, value_text=rest.strip(), recorded_at=recorded_at
            )
        except ValueError as e:
            await message.answer(str(e))
            return

    await message.answer(
        f"Backfilled {METRIC_LABELS[metric]} for {dto.entry_date.isoformat()}."
    )
