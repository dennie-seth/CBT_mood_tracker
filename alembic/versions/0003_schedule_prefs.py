"""schedule_prefs table for automated daily/weekly Haiku summaries

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-04 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_prefs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "daily_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("daily_at", sa.Time(), nullable=True),
        sa.Column("daily_last_sent_date", sa.Date(), nullable=True),
        sa.Column(
            "weekly_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("weekly_weekday", sa.SmallInteger(), nullable=True),
        sa.Column("weekly_at", sa.Time(), nullable=True),
        sa.Column("weekly_last_sent_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_schedule_prefs_daily_enabled",
        "schedule_prefs",
        ["daily_enabled"],
        postgresql_where=sa.text("daily_enabled"),
    )
    op.create_index(
        "ix_schedule_prefs_weekly_enabled",
        "schedule_prefs",
        ["weekly_enabled"],
        postgresql_where=sa.text("weekly_enabled"),
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_prefs_weekly_enabled", table_name="schedule_prefs")
    op.drop_index("ix_schedule_prefs_daily_enabled", table_name="schedule_prefs")
    op.drop_table("schedule_prefs")
