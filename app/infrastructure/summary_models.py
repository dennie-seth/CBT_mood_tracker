from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import Base

# BIGINT on Postgres; INTEGER on SQLite so the in-memory test DB autoincrements
# the surrogate key (SQLite only auto-assigns INTEGER PRIMARY KEY).
_AutoIntPk = BigInteger().with_variant(Integer, "sqlite")


class WeeklySummary(Base):
    """A persisted weekly Haiku summary, giving the weekly digest a memory.

    The text references personal events, so it is stored encrypted with the
    same `FernetCipher` as entries — the column only ever holds ciphertext.
    Encryption/decryption is the caller's responsibility (SummaryService is
    the chokepoint), mirroring how `Entry.value_text_encrypted` works.

    `week_start` / `week_end` bound the 7-day window the summary covers,
    interpreted in the owning user's `User.timezone`. Rows are read back
    newest-first to feed the last few weeks as continuity context.
    """

    __tablename__ = "weekly_summaries"

    id: Mapped[int] = mapped_column(_AutoIntPk, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    summary_text_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_weekly_summaries_user_created", "user_id", "created_at"),
    )
