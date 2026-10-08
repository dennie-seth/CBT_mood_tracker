from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.chat_log_models import ChatMessage

RETENTION = timedelta(hours=48)


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


class SqlChatLogRepository:
    """Message ids (never content) of the last 48h, per private chat."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, chat_id: int, message_id: int, *, at: datetime) -> None:
        at = _utc(at)
        exists = await self._session.scalar(
            select(ChatMessage.message_id).where(
                ChatMessage.chat_id == chat_id, ChatMessage.message_id == message_id
            )
        )
        if exists is None:
            self._session.add(ChatMessage(chat_id=chat_id, message_id=message_id, created_at=at))
        # Opportunistic prune — no scheduler needed (same idea as fsm_state).
        await self._session.execute(
            delete(ChatMessage).where(ChatMessage.created_at < at - RETENTION)
        )
        await self._session.flush()

    async def ids_since(self, chat_id: int, since: datetime) -> list[int]:
        result = await self._session.execute(
            select(ChatMessage.message_id)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.created_at >= _utc(since))
            .order_by(ChatMessage.message_id)
        )
        return list(result.scalars().all())

    async def ids_between(self, chat_id: int, first_id: int, last_id: int) -> list[int]:
        result = await self._session.execute(
            select(ChatMessage.message_id)
            .where(
                ChatMessage.chat_id == chat_id,
                ChatMessage.message_id >= first_id,
                ChatMessage.message_id <= last_id,
            )
            .order_by(ChatMessage.message_id)
        )
        return list(result.scalars().all())

    async def forget(self, chat_id: int, message_ids: list[int]) -> None:
        if message_ids:
            await self._session.execute(
                delete(ChatMessage).where(
                    ChatMessage.chat_id == chat_id, ChatMessage.message_id.in_(message_ids)
                )
            )
