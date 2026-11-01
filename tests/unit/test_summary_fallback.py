"""SummaryService must not treat AiService's canned fallback (refusal /
iteration limit) as a real summary: no storage, no send, no stamp — until a
small retry cap is hit, after which the slot is stamped (still without
storing or sending) so the 60 s scheduler tick can't loop all day.
"""
from __future__ import annotations

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.tools import ToolArtifact
from app.domain.models import User
from app.infrastructure.repositories.schedule_repo import SqlScheduleRepository
from app.infrastructure.repositories.weekly_summary_repo import SqlWeeklySummaryRepository
from app.services.ai_service import AiAnswer
from app.services.summary_service import MAX_FALLBACK_ATTEMPTS, SummaryService

CANNED = "Sorry, I couldn't answer that one. Could you rephrase the question?"


async def _make_user(sm) -> User:
    async with sm() as session:
        u = User(id=42, telegram_id=555, display_name="t", timezone="Europe/Berlin")
        session.add(u)
        await session.commit()
        await session.refresh(u)
    async with sm() as session:
        repo = SqlScheduleRepository(session)
        await repo.set_daily(u.id, enabled=True, at=time(21, 0))
        await session.commit()
    return u


def _fallback_ai() -> AsyncMock:
    art = ToolArtifact(kind="image/png", filename="c.png", data=b"\x89PNG")
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text=CANNED, artifacts=[art], fallback=True))
    return ai


def _svc(sm, ai, bot, cipher) -> SummaryService:
    return SummaryService(
        ai_service=ai,
        sessionmaker=sm,
        cipher=cipher,
        chart_service=MagicMock(),
        pdf_service=MagicMock(),
        bot=bot,
    )


async def _prefs(sm, user_id: int):
    async with sm() as session:
        return await SqlScheduleRepository(session).get(user_id)


@pytest.mark.parametrize("kind", ["daily", "weekly"])
async def test_fallback_answer_is_not_stored_sent_or_stamped(schedule_sm, cipher, kind) -> None:
    user = await _make_user(schedule_sm)
    bot = AsyncMock()
    svc = _svc(schedule_sm, _fallback_ai(), bot, cipher)

    await svc.send(user, kind=kind, local_today=date(2026, 5, 10))

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=5)
    assert rows == []
    bot.send_message.assert_not_awaited()
    bot.send_photo.assert_not_awaited()
    bot.send_document.assert_not_awaited()
    prefs = await _prefs(schedule_sm, user.id)
    assert prefs is not None
    assert prefs.daily_last_sent_date is None
    assert prefs.weekly_last_sent_date is None


async def test_fallback_retries_are_capped_then_slot_is_stamped(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    bot = AsyncMock()
    ai = _fallback_ai()
    svc = _svc(schedule_sm, ai, bot, cipher)
    day = date(2026, 5, 10)

    for _ in range(MAX_FALLBACK_ATTEMPTS - 1):
        await svc.send(user, kind="weekly", local_today=day)
    prefs = await _prefs(schedule_sm, user.id)
    assert prefs is not None and prefs.weekly_last_sent_date is None

    await svc.send(user, kind="weekly", local_today=day)

    prefs = await _prefs(schedule_sm, user.id)
    assert prefs is not None
    assert prefs.weekly_last_sent_date == day  # scheduler stops retrying today
    assert prefs.daily_last_sent_date is None
    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=5)
    assert rows == []  # canned line never becomes "memory"
    bot.send_message.assert_not_awaited()
    assert ai.answer.await_count == MAX_FALLBACK_ATTEMPTS


async def test_success_after_a_fallback_delivers_normally(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    bot = AsyncMock()
    ai = AsyncMock()
    ai.answer = AsyncMock(side_effect=[
        AiAnswer(text=CANNED, artifacts=[], fallback=True),
        AiAnswer(text="Real summary.", artifacts=[]),
    ])
    svc = _svc(schedule_sm, ai, bot, cipher)
    day = date(2026, 5, 10)

    await svc.send(user, kind="weekly", local_today=day)
    await svc.send(user, kind="weekly", local_today=day)

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=5)
    assert [cipher.decrypt(r.summary_text_encrypted) for r in rows] == ["Real summary."]
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args.kwargs["text"] == "Real summary."
