"""fsm_state table for persistent aiogram FSM storage

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-04 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fsm_state",
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "thread_id", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "business_connection_id",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "destiny", sa.Text(), nullable=False, server_default="default"
        ),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("data_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "bot_id",
            "chat_id",
            "user_id",
            "thread_id",
            "business_connection_id",
            "destiny",
        ),
    )
    op.create_index("ix_fsm_state_updated_at", "fsm_state", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_fsm_state_updated_at", table_name="fsm_state")
    op.drop_table("fsm_state")
