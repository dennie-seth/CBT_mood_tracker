from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import Base


class ChatMessage(Base):
    """Ids of recent messages in private chats with the bot — NO content.

    Lets /hide and auto-tidy delete exactly this chat's messages (Telegram
    message ids aren't contiguous per private chat). Rows older than 48h are
    pruned on write: Telegram won't let bots delete older messages anyway.
    """

    __tablename__ = "chat_messages"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_chat_messages_created_at", "created_at"),)
