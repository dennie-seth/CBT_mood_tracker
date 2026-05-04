from __future__ import annotations

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.summary_prompts import DAILY_PROMPT, WEEKLY_PROMPT
from app.ai.tools import ToolArtifact
from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.services.ai_service import AiAnswer
from app.services.summary_service import SummaryService


async def _make_user(sm, telegram_id: int = 555) -> User:
    async with sm() as session:
        u = User(id=42, telegram_id=telegram_id, display_name="t", timezone="Europe/Berlin")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


def _build_service(sm, ai, bot, cipher):
    return SummaryService(
        ai_service=ai,
        sessionmaker=sm,
        cipher=cipher,
        chart_service=MagicMock(),
        pdf_service=MagicMock(),
        bot=bot,
    )


async def test_daily_send_calls_ai_with_daily_prompt(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="Today was solid.", artifacts=[]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="daily", local_today=date(2026, 5, 4))

    ai.answer.assert_awaited_once()
    args, kwargs = ai.answer.call_args
    assert kwargs.get("question", args[0] if args else None) == DAILY_PROMPT
    assert kwargs.get("today", args[2] if len(args) > 2 else None) == date(2026, 5, 4)


async def test_weekly_send_uses_weekly_prompt(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="Week trended up.", artifacts=[]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    args, kwargs = ai.answer.call_args
    assert kwargs.get("question", args[0] if args else None) == WEEKLY_PROMPT


async def test_send_delivers_text_to_user_chat(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm, telegram_id=555)
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="Hi!", artifacts=[]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="daily", local_today=date(2026, 5, 4))

    bot.send_message.assert_awaited_once()
    _, kwargs = bot.send_message.call_args
    assert kwargs["chat_id"] == 555
    assert kwargs["text"] == "Hi!"


async def test_send_forwards_png_artifact_as_photo(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm, telegram_id=555)
    art = ToolArtifact(kind="image/png", filename="chart.png", data=b"\x89PNG\r\n\x1a\n...")
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="See chart", artifacts=[art]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    bot.send_photo.assert_awaited_once()
    bot.send_document.assert_not_awaited()
    _, kwargs = bot.send_photo.call_args
    assert kwargs["chat_id"] == 555


async def test_send_forwards_pdf_artifact_as_document(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm, telegram_id=555)
    art = ToolArtifact(kind="application/pdf", filename="r.pdf", data=b"%PDF-1.4...")
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="See PDF", artifacts=[art]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    bot.send_document.assert_awaited_once()
    bot.send_photo.assert_not_awaited()


async def test_send_stamps_last_sent_after_success(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text="ok", artifacts=[]))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    await svc.send(user, kind="daily", local_today=date(2026, 5, 4))

    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date == date(2026, 5, 4)
    assert prefs.weekly_last_sent_date is None


async def test_send_does_not_stamp_when_ai_raises(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)

    # Pre-existing prefs row so we can inspect it later — no last-sent date yet.
    async with schedule_sm() as session:
        await SqlScheduleRepository(session).set_daily(user.id, enabled=True, at=time(21, 0))
        await session.commit()

    ai = AsyncMock()
    ai.answer = AsyncMock(side_effect=RuntimeError("boom"))
    bot = AsyncMock()
    svc = _build_service(schedule_sm, ai, bot, cipher)

    with pytest.raises(RuntimeError):
        await svc.send(user, kind="daily", local_today=date(2026, 5, 4))

    bot.send_message.assert_not_awaited()
    async with schedule_sm() as session:
        prefs = await SqlScheduleRepository(session).get(user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date is None
