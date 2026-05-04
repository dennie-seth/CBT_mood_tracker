from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import Base


class FsmState(Base):
    """Persistent backing for aiogram's FSM storage.

    The composite PK mirrors `aiogram.fsm.storage.base.StorageKey`.
    `thread_id` and `business_connection_id` are coalesced from NULL to
    sentinel values (0 and "") so the PK stays simple without partial
    unique indexes.

    `data_encrypted` holds `Fernet(json.dumps(data))` — never plaintext —
    because mid-flow content for /thought etc. is sensitive.
    """

    __tablename__ = "fsm_state"

    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, server_default="0"
    )
    business_connection_id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=""
    )
    destiny: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default="default"
    )

    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_fsm_state_updated_at", "updated_at"),)
