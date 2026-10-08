"""Storage behind /hide, auto-tidy and /pause.

chat_messages keeps ONLY (chat_id, message_id, created_at) for the last 48h
— Telegram won't let bots delete older messages anyway — so /hide and
auto-tidy can delete exactly this chat's messages. No content is stored.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessages

from app.bot.chat_cleanup import clear_chat, tidy_span
from app.domain.models import User
from app.infrastructure.repositories.chat_log_repo import SqlChatLogRepository
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.schedule_service import SummaryScheduler

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


async def _record(sm, chat_id: int, ids, at: datetime = NOW) -> None:
    async with sm() as s:
        repo = SqlChatLogRepository(s)
        for i in ids:
            await repo.record(chat_id, i, at=at)
        await s.commit()


async def _ids(sm, chat_id: int) -> list[int]:
    async with sm() as s:
        return await SqlChatLogRepository(s).ids_since(chat_id, NOW - timedelta(days=3))


# --- chat log --------------------------------------------------------------

async def test_record_is_idempotent_and_per_chat(schedule_sm) -> None:
    await _record(schedule_sm, 1, [10, 11, 11])
    await _record(schedule_sm, 2, [12])
    assert await _ids(schedule_sm, 1) == [10, 11]


async def test_old_rows_are_pruned_on_write(schedule_sm) -> None:
    await _record(schedule_sm, 1, [5], at=NOW - timedelta(hours=49))
    await _record(schedule_sm, 1, [6], at=NOW)
    assert await _ids(schedule_sm, 1) == [6]


async def test_ids_between(schedule_sm) -> None:
    await _record(schedule_sm, 1, [10, 13, 20, 25])
    async with schedule_sm() as s:
        assert await SqlChatLogRepository(s).ids_between(1, 13, 20) == [13, 20]


# --- clear_chat / tidy_span --------------------------------------------------

async def test_clear_chat_deletes_tracked_ids_in_chunks(schedule_sm) -> None:
    await _record(schedule_sm, 1, range(1, 151))
    await _record(schedule_sm, 2, [999])
    bot = AsyncMock()
    deleted = await clear_chat(bot, schedule_sm, chat_id=1, now=NOW)

    assert deleted == 150
    calls = bot.delete_messages.await_args_list
    assert len(calls) == 2
    assert all(len(c.kwargs["message_ids"]) <= 100 for c in calls)
    assert all(c.kwargs["chat_id"] == 1 for c in calls)
    assert await _ids(schedule_sm, 1) == []
    assert await _ids(schedule_sm, 2) == [999]  # other chats untouched


async def test_clear_chat_survives_telegram_errors(schedule_sm) -> None:
    await _record(schedule_sm, 1, [1, 2, 3])
    bot = AsyncMock()
    bot.delete_messages.side_effect = TelegramBadRequest(
        method=DeleteMessages(chat_id=1, message_ids=[1]), message="too old"
    )
    await clear_chat(bot, schedule_sm, chat_id=1, now=NOW)  # must not raise
    assert await _ids(schedule_sm, 1) == []


async def test_tidy_span_deletes_only_that_span(schedule_sm) -> None:
    await _record(schedule_sm, 1, [10, 11, 12, 30])
    bot = AsyncMock()
    await tidy_span(bot, schedule_sm, chat_id=1, first_id=10, last_id=12, delay=0)
    assert bot.delete_messages.await_args.kwargs["message_ids"] == [10, 11, 12]
    assert await _ids(schedule_sm, 1) == [30]


# --- prefs: pause + tidy -----------------------------------------------------

async def _user(sm, id: int, tg: int) -> User:
    async with sm() as s:
        u = User(id=id, telegram_id=tg, display_name=f"u{id}", timezone="UTC")
        s.add(u)
        await s.commit()
        return u


async def test_pause_and_resume(schedule_sm) -> None:
    await _user(schedule_sm, 1, 111)
    await _user(schedule_sm, 2, 222)
    async with schedule_sm() as s:
        repo = SqlScheduleRepository(s)
        await repo.set_pause(1, until=NOW + timedelta(days=3))
        await repo.set_pause(2, until=NOW - timedelta(minutes=1))  # already over
        await s.commit()
    async with schedule_sm() as s:
        assert await SqlScheduleRepository(s).paused_user_ids(NOW) == {1}
        await SqlScheduleRepository(s).set_pause(1, until=None)
        await s.commit()
    async with schedule_sm() as s:
        assert await SqlScheduleRepository(s).paused_user_ids(NOW) == set()


async def test_tidy_flag(schedule_sm) -> None:
    await _user(schedule_sm, 1, 111)
    async with schedule_sm() as s:
        repo = SqlScheduleRepository(s)
        assert await repo.tidy_enabled(1) is False
        await repo.set_tidy(1, enabled=True)
        await s.commit()
    async with schedule_sm() as s:
        assert await SqlScheduleRepository(s).tidy_enabled(1) is True


async def test_scheduler_skips_everything_for_paused_users(schedule_sm) -> None:
    await _user(schedule_sm, 1, 111)
    async with schedule_sm() as s:
        repo = SqlScheduleRepository(s)
        await repo.set_daily(1, enabled=True, at=time(9, 0))
        await repo.set_checkins(1, enabled=True)
        await repo.set_pause(1, until=NOW + timedelta(days=1))
        await s.commit()

    delivery, probe, reminder = AsyncMock(), AsyncMock(), AsyncMock()
    scheduler = SummaryScheduler(
        sessionmaker=schedule_sm, delivery=delivery,
        checkin_probe=probe, migraine_reminder=reminder,
    )
    await scheduler.dispatch_due(NOW)
    delivery.assert_not_awaited()
    probe.assert_not_awaited()
    reminder.assert_not_awaited()

    # After the pause ends everything resumes on its own.
    await scheduler.dispatch_due(NOW + timedelta(days=2))
    assert delivery.await_count == 1
    assert probe.await_count == 1
    assert reminder.await_count == 1


@pytest.mark.parametrize("private,tracked", [(True, True), (False, False)])
async def test_incoming_tracking_middleware(schedule_sm, private, tracked) -> None:
    from unittest.mock import MagicMock

    from aiogram.types import Message

    from app.bot.middlewares.chat_log import IncomingChatLogMiddleware

    mw = IncomingChatLogMiddleware(schedule_sm)
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock(id=5, type="private" if private else "group")
    msg.message_id = 77
    handler = AsyncMock(return_value="ok")
    assert await mw(handler, msg, {}) == "ok"
    assert (await _ids(schedule_sm, 5) == [77]) is tracked


async def test_outgoing_tracking_request_middleware(schedule_sm) -> None:
    from unittest.mock import MagicMock

    from aiogram.methods import SendMessage
    from aiogram.types import Message

    from app.bot.middlewares.chat_log import OutgoingChatLogMiddleware

    sent = MagicMock(spec=Message)
    sent.chat = MagicMock(id=5, type="private")
    sent.message_id = 78
    make_request = AsyncMock(return_value=sent)
    mw = OutgoingChatLogMiddleware(schedule_sm)
    result = await mw(make_request, MagicMock(), SendMessage(chat_id=5, text="hi"))
    assert result is sent
    assert await _ids(schedule_sm, 5) == [78]
