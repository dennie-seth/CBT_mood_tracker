"""chat_messages (ids only, 48h) + schedule_prefs.paused_until / tidy_enabled

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-08 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.add_column(
        "schedule_prefs",
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "schedule_prefs",
        sa.Column(
            "tidy_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("schedule_prefs", "tidy_enabled")
    op.drop_column("schedule_prefs", "paused_until")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
