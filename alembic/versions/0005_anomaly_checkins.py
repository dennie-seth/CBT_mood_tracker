"""add schedule_prefs.checkins_enabled + checkins_last_sent_at

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-04 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedule_prefs",
        sa.Column(
            "checkins_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "schedule_prefs",
        sa.Column(
            "checkins_last_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_schedule_prefs_checkins_enabled",
        "schedule_prefs",
        ["checkins_enabled"],
        postgresql_where=sa.text("checkins_enabled"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_prefs_checkins_enabled", table_name="schedule_prefs"
    )
    op.drop_column("schedule_prefs", "checkins_last_sent_at")
    op.drop_column("schedule_prefs", "checkins_enabled")
