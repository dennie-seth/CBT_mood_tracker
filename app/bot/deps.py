from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User
from app.infrastructure.repositories.entry_repo import SqlEntryRepository
from app.services.entry_service import EntryService


def entry_service(session: AsyncSession, cipher) -> EntryService:
    return EntryService(SqlEntryRepository(session), cipher)


def get_user(data: dict) -> User:
    user = data.get("user")
    if user is None:
        raise RuntimeError("UserContextMiddleware did not populate data['user']")
    return user
