from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domain.models import User
from app.infrastructure.crypto import FernetCipher
from app.infrastructure.fsm_models import FsmState
from app.infrastructure.schedule_models import SchedulePrefs


@pytest_asyncio.fixture()
async def fsm_sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """SQLite in-memory engine with only the fsm_state table created.

    We don't run all of Base.metadata.create_all because Entry uses
    Postgres-only ARRAY/JSONB types that won't compile under SQLite.
    fsm_state itself uses portable types (BigInteger, Text, LargeBinary,
    DateTime), so it works on both Postgres in production and SQLite in tests.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(FsmState.__table__.create)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sm
    finally:
        await engine.dispose()


@pytest.fixture()
def cipher() -> FernetCipher:
    return FernetCipher([Fernet.generate_key().decode()])


@pytest_asyncio.fixture()
async def schedule_sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """SQLite in-memory engine with `users` + `schedule_prefs` tables only.

    Skips Entry (Postgres-only ARRAY/JSONB) and FsmState (not needed here)
    so each test starts with a minimal, fast schema.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        await conn.run_sync(SchedulePrefs.__table__.create)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sm
    finally:
        await engine.dispose()
