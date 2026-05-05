from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.crypto import FernetCipher
from app.infrastructure.fsm_models import FsmState

log = structlog.get_logger(__name__)


class PgFsmStorage(BaseStorage):
    """Persistent FSM storage backed by Postgres (SQLite-compatible for tests).

    `state` is stored as a plain string, `data` as Fernet-encrypted JSON so
    sensitive in-flight content (e.g. /thought reflections) never lands in
    the DB as plaintext.
    """

    CLEANUP_INTERVAL: timedelta = timedelta(days=7)

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        cipher: FernetCipher,
    ) -> None:
        self._sm = sessionmaker
        self._cipher = cipher

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_str = state.state if isinstance(state, State) else state
        await self._upsert(key, state=state_str, data_encrypted=_UNSET)

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._sm() as session:
            row = await session.scalar(self._select_pk(key))
            return row.state if row is not None else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        encrypted = self._cipher.encrypt_json(dict(data)) if data else None
        await self._upsert(key, state=_UNSET, data_encrypted=encrypted)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._sm() as session:
            row = await session.scalar(self._select_pk(key))
            if row is None or row.data_encrypted is None:
                return {}
            try:
                payload = self._cipher.decrypt_json(row.data_encrypted)
            except ValueError:
                # Survive key rotation: an old in-flight blob encrypted with a
                # key that's no longer present must not crash the bot. Treat
                # the row as absent and self-heal by deleting it so the next
                # write to this key starts fresh.
                log.warning(
                    "fsm_state_unreadable_after_key_rotation",
                    bot_id=key.bot_id,
                    chat_id=key.chat_id,
                    user_id=key.user_id,
                )
                await session.delete(row)
                await session.commit()
                return {}
            return dict(payload) if isinstance(payload, dict) else {}

    async def close(self) -> None:
        # The engine is owned by the DI Container; nothing to release here.
        return None

    async def _upsert(
        self,
        key: StorageKey,
        *,
        state: str | None | object,
        data_encrypted: bytes | None | object,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._sm() as session:
            row = await session.scalar(self._select_pk(key))

            # Compute what the row would hold after applying this update.
            new_state = state if state is not _UNSET else (
                row.state if row is not None else None
            )
            new_data = data_encrypted if data_encrypted is not _UNSET else (
                row.data_encrypted if row is not None else None
            )

            if new_state is None and new_data is None:
                # The row would carry nothing — delete it if it exists in the
                # DB. If we never had a row, do nothing (NOT add+delete: a
                # transient row is "pending" and `session.delete()` would
                # raise "Instance is not persisted"; this regression bit the
                # /note two-step flow because aiogram's `FSMContext.clear()`
                # calls `set_state(None)` then `set_data({})` back-to-back,
                # and the second call lands here with no row in the DB).
                if row is not None:
                    await session.delete(row)
                await self._cleanup(session, now)
                await session.commit()
                return

            if row is None:
                row = FsmState(**self._pk_dict(key))
                session.add(row)
            row.state = new_state  # type: ignore[assignment]
            row.data_encrypted = new_data  # type: ignore[assignment]
            row.updated_at = now

            await self._cleanup(session, now)
            await session.commit()

    async def _cleanup(self, session: AsyncSession, now: datetime) -> None:
        cutoff = now - self.CLEANUP_INTERVAL
        await session.execute(
            delete(FsmState).where(FsmState.updated_at < cutoff)
        )

    def _select_pk(self, key: StorageKey):
        pk = self._pk_dict(key)
        return select(FsmState).where(
            FsmState.bot_id == pk["bot_id"],
            FsmState.chat_id == pk["chat_id"],
            FsmState.user_id == pk["user_id"],
            FsmState.thread_id == pk["thread_id"],
            FsmState.business_connection_id == pk["business_connection_id"],
            FsmState.destiny == pk["destiny"],
        )

    @staticmethod
    def _pk_dict(key: StorageKey) -> dict[str, Any]:
        return {
            "bot_id": key.bot_id,
            "chat_id": key.chat_id,
            "user_id": key.user_id,
            "thread_id": key.thread_id or 0,
            "business_connection_id": key.business_connection_id or "",
            "destiny": key.destiny,
        }


# Sentinel for "leave the column unchanged" in the upsert helper. Using a
# private object lets us distinguish "set this column to None" from "don't
# touch this column".
_UNSET: Any = object()
