from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers import (
    activate,
    ask,
    backfill,
    chart,
    day,
    entry_actions,
    checkins,
    export,
    home,
    journal,
    lang,
    log,
    migraine,
    plain,
    quick,
    recent,
    schedule,
    start,
    therapist,
    today,
    tz,
)


def register_all(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(home.router)  # before flows: shortcut taps win
    dp.include_router(entry_actions.router)
    dp.include_router(quick.router)  # quick shortcuts before generic /log
    dp.include_router(log.router)
    dp.include_router(backfill.router)
    dp.include_router(journal.router)
    dp.include_router(activate.router)
    dp.include_router(day.router)
    dp.include_router(recent.router)
    dp.include_router(migraine.router)
    dp.include_router(today.router)
    dp.include_router(tz.router)
    dp.include_router(lang.router)
    dp.include_router(schedule.router)
    dp.include_router(checkins.router)
    dp.include_router(ask.router)
    dp.include_router(chart.router)
    dp.include_router(export.router)
    dp.include_router(therapist.router)
    dp.include_router(plain.router)  # last: free text nobody else claimed
