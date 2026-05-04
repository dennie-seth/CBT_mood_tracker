from __future__ import annotations

from datetime import datetime, time

import pytz
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.deps import entry_service
from app.bot.i18n import metric_label, t
from app.domain.enums import NUMERIC_METRICS, MetricType
from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.services.time import parse_relative_date

router = Router()


def split_backfill_args(args: str) -> tuple[str, str, str]:
    """Split '/backfill <date> <metric> <value>' args.

    Recognises the 3-token 'N day(s) ago' phrase explicitly.
    Raises ValueError on too few tokens.
    """
    tokens = args.split()
    if len(tokens) < 3:
        raise ValueError("too few tokens")
    if (
        len(tokens) >= 5
        and tokens[1].lower() in ("day", "days")
        and tokens[2].lower() == "ago"
    ):
        return " ".join(tokens[:3]), tokens[3], " ".join(tokens[4:])
    return tokens[0], tokens[1], " ".join(tokens[2:])


def _local_noon_utc(d, tz_name: str) -> datetime:
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
        await message.answer(t(user.language, "backfill.usage"))
        return

    try:
        date_str, metric_str, rest = split_backfill_args(command.args)
    except ValueError:
        await message.answer(t(user.language, "backfill.usage"))
        return

    try:
        target_date = parse_relative_date(date_str, user.timezone)
    except ValueError as e:
        await message.answer(
            t(user.language, "backfill.bad_date", raw=date_str, err=e)
        )
        return

    try:
        metric = MetricType(metric_str)
    except ValueError:
        await message.answer(
            t(
                user.language, "backfill.bad_metric",
                raw=metric_str,
                choices=", ".join(m.value for m in MetricType),
            )
        )
        return

    svc = entry_service(session, cipher)
    recorded_at = _local_noon_utc(target_date, user.timezone)
    label = metric_label(metric, user.language)

    if metric in NUMERIC_METRICS:
        try:
            value = float(rest.replace(",", "."))
        except ValueError:
            await message.answer(t(user.language, "backfill.bad_value", raw=rest))
            return
        try:
            dto = await svc.create(
                user, metric, value_numeric=value, recorded_at=recorded_at
            )
        except ValueError as e:
            await message.answer(str(e))
            return
        await message.answer(
            t(
                user.language, "backfill.saved_numeric",
                label=label, value=value, date=dto.entry_date.isoformat(),
            )
        )
        return

    text = rest.strip()
    if not text:
        await message.answer(t(user.language, "backfill.need_text", label=label))
        return
    try:
        dto = await svc.create(
            user, metric, value_text=text, recorded_at=recorded_at
        )
    except ValueError as e:
        await message.answer(str(e))
        return
    await message.answer(
        t(
            user.language, "backfill.saved_text",
            label=label, date=dto.entry_date.isoformat(),
        )
    )
