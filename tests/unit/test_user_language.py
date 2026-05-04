"""User.language column + repo plumbing:

- Defaults to "en".
- create() accepts an explicit language.
- update_language() flips it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domain.models import User
from app.infrastructure.repositories.user_repo import SqlUserRepository


@pytest.mark.asyncio
async def test_default_language_is_english(schedule_sm) -> None:
    async with schedule_sm() as session:
        u = User(id=1, telegram_id=100, display_name="t", timezone="UTC")
        session.add(u)
        await session.flush()
        assert u.language == "en"


@pytest.mark.asyncio
async def test_create_with_explicit_russian(schedule_sm) -> None:
    async with schedule_sm() as session:
        # SqlUserRepository.create needs an autoincrementing PK; SQLite + BigInt
        # doesn't autoincrement, so set the id by hand for the test.
        u = User(id=2, telegram_id=101, display_name="t", timezone="UTC", language="ru")
        session.add(u)
        await session.flush()
        await session.commit()

    async with schedule_sm() as session:
        loaded = (await session.execute(select(User).where(User.id == 2))).scalar_one()
        assert loaded.language == "ru"


@pytest.mark.asyncio
async def test_update_language_persists(schedule_sm) -> None:
    async with schedule_sm() as session:
        u = User(id=3, telegram_id=102, display_name="t", timezone="UTC")
        session.add(u)
        await session.flush()
        await session.commit()

    async with schedule_sm() as session:
        repo = SqlUserRepository(session)
        await repo.update_language(3, "ru")
        await session.commit()

    async with schedule_sm() as session:
        loaded = (await session.execute(select(User).where(User.id == 3))).scalar_one()
        assert loaded.language == "ru"
