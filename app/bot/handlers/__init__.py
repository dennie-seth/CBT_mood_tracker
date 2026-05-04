from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers import (
    activate,
    ask,
    backfill,
    chart,
    export,
    journal,
    log,
    quick,
    schedule,
    start,
    today,
    tz,
)


def register_all(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(quick.router)  # quick shortcuts before generic /log
    dp.include_router(log.router)
    dp.include_router(backfill.router)
    dp.include_router(journal.router)
    dp.include_router(activate.router)
    dp.include_router(today.router)
    dp.include_router(tz.router)
    dp.include_router(schedule.router)
    dp.include_router(ask.router)
    dp.include_router(chart.router)
    dp.include_router(export.router)
