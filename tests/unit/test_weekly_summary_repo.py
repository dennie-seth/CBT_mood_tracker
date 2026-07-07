from __future__ import annotations

from datetime import date

from app.domain.models import User
from app.infrastructure.repositories.weekly_summary_repo import SqlWeeklySummaryRepository


async def _make_user(sm, *, id: int = 1, telegram_id: int = 1) -> User:
    async with sm() as session:
        u = User(id=id, telegram_id=telegram_id, display_name="t", timezone="UTC")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return u


async def test_add_then_latest_roundtrips_row(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        await SqlWeeklySummaryRepository(session).add(
            user.id,
            week_start=date(2026, 4, 27),
            week_end=date(2026, 5, 3),
            summary_text_encrypted=b"\x00ciphertext\xff",
        )
        await session.commit()

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=3)

    assert len(rows) == 1
    assert rows[0].summary_text_encrypted == b"\x00ciphertext\xff"
    assert rows[0].week_start == date(2026, 4, 27)
    assert rows[0].week_end == date(2026, 5, 3)


async def test_latest_returns_newest_first_and_honours_limit(schedule_sm) -> None:
    user = await _make_user(schedule_sm)
    async with schedule_sm() as session:
        repo = SqlWeeklySummaryRepository(session)
        for i in range(1, 5):
            await repo.add(
                user.id,
                week_start=date(2026, 5, i),
                week_end=date(2026, 5, i + 6),
                summary_text_encrypted=f"w{i}".encode(),
            )
        await session.commit()

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(user.id, limit=2)

    assert [r.summary_text_encrypted for r in rows] == [b"w4", b"w3"]


async def test_latest_is_scoped_to_the_user(schedule_sm) -> None:
    u1 = await _make_user(schedule_sm, id=1, telegram_id=1)
    u2 = await _make_user(schedule_sm, id=2, telegram_id=2)
    async with schedule_sm() as session:
        repo = SqlWeeklySummaryRepository(session)
        await repo.add(
            u1.id, week_start=date(2026, 5, 1), week_end=date(2026, 5, 7),
            summary_text_encrypted=b"u1",
        )
        await repo.add(
            u2.id, week_start=date(2026, 5, 1), week_end=date(2026, 5, 7),
            summary_text_encrypted=b"u2",
        )
        await session.commit()

    async with schedule_sm() as session:
        rows = await SqlWeeklySummaryRepository(session).latest(u1.id, limit=5)

    assert [r.summary_text_encrypted for r in rows] == [b"u1"]
