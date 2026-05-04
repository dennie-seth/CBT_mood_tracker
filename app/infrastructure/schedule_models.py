from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import Base


class SchedulePrefs(Base):
    """Per-user scheduling preferences for automated Haiku summaries.

    Times are stored as naive `TIME` values, interpreted in the owning
    user's `User.timezone`. `*_last_sent_date` is also a date in the
    user's tz, used as an idempotency guard so a bot restart at the
    trigger minute doesn't double-deliver.
    """

    __tablename__ = "schedule_prefs"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    daily_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    daily_at: Mapped[time | None] = mapped_column(Time, nullable=True)
    daily_last_sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    weekly_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    weekly_weekday: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    weekly_at: Mapped[time | None] = mapped_column(Time, nullable=True)
    weekly_last_sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_schedule_prefs_daily_enabled",
            "daily_enabled",
            postgresql_where="daily_enabled",
        ),
        Index(
            "ix_schedule_prefs_weekly_enabled",
            "weekly_enabled",
            postgresql_where="weekly_enabled",
        ),
    )
