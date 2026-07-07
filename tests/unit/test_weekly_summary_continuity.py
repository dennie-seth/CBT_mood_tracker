from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.ai.summary_prompts import WEEKLY_PROMPT
from app.domain.models import User
from app.infrastructure.repositories.weekly_summary_repo import SqlWeeklySummaryRepository
from app.services.ai_service import AiAnswer
from app.services.summary_service import SummaryService


async def _make_user(sm, *, id: int = 42, telegram_id: int = 555) -> User:
    async with sm() as session:
        u = User(id=id, telegram_id=telegram_id, display_name="t", timezone="Europe/Berlin")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


def _svc(sm, ai, cipher) -> SummaryService:
    return SummaryService(
        ai_service=ai,
        sessionmaker=sm,
        cipher=cipher,
        chart_service=MagicMock(),
        pdf_service=MagicMock(),
        bot=AsyncMock(),
    )


def _ai(text: str) -> AsyncMock:
    ai = AsyncMock()
    ai.answer = AsyncMock(return_value=AiAnswer(text=text, artifacts=[]))
    return ai


async def test_weekly_persists_summary_encrypted_at_rest(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = _ai("Mood climbed after the walk on Tuesday.")
    svc = _svc(schedule_sm, ai, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=5)

    assert len(rows) == 1
    stored = rows[0].summary_text_encrypted
    # Never plaintext at rest.
    assert b"Mood climbed" not in stored
    assert cipher.decrypt(stored) == "Mood climbed after the walk on Tuesday."
    # 7-day window ending on the fire date.
    assert rows[0].week_start == date(2026, 5, 4)
    assert rows[0].week_end == date(2026, 5, 10)


async def test_weekly_feeds_prior_summaries_into_the_prompt(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        await SqlWeeklySummaryRepository(session).add(
            user.id,
            week_start=date(2026, 4, 27),
            week_end=date(2026, 5, 3),
            summary_text_encrypted=cipher.encrypt("Last week you focused on sleep hygiene."),
        )
        await session.commit()

    ai = _ai("This week built on it.")
    svc = _svc(schedule_sm, ai, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    question = ai.answer.call_args.kwargs["question"]
    assert "sleep hygiene" in question       # decrypted prior summary as context
    assert "2026-04-27" in question           # the prior week's range
    assert WEEKLY_PROMPT in question          # instructions still present


async def test_weekly_first_ever_uses_bare_prompt(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = _ai("First week.")
    svc = _svc(schedule_sm, ai, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    assert ai.answer.call_args.kwargs["question"] == WEEKLY_PROMPT


async def test_weekly_loads_only_the_most_recent_three(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlWeeklySummaryRepository(session)
        for i in range(1, 6):  # five prior weeks
            await repo.add(
                user.id,
                week_start=date(2026, 3, i),
                week_end=date(2026, 3, i + 6),
                summary_text_encrypted=cipher.encrypt(f"week {i} note"),
            )
        await session.commit()

    ai = _ai("ok")
    svc = _svc(schedule_sm, ai, cipher)

    await svc.send(user, kind="weekly", local_today=date(2026, 5, 10))

    question = ai.answer.call_args.kwargs["question"]
    assert "week 5 note" in question and "week 4 note" in question and "week 3 note" in question
    assert "week 1 note" not in question and "week 2 note" not in question
    # Chronological order in the context (older week appears before newer).
    assert question.index("week 3 note") < question.index("week 5 note")


async def test_daily_does_not_persist_a_weekly_summary(schedule_sm, cipher) -> None:
    user = await _make_user(schedule_sm)
    ai = _ai("Daily digest.")
    svc = _svc(schedule_sm, ai, cipher)

    await svc.send(user, kind="daily", local_today=date(2026, 5, 10))

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=5)
    assert rows == []
