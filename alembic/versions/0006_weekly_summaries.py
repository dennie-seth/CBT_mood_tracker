"""add weekly_summaries table (encrypted weekly digest memory)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weekly_summaries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("summary_text_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_weekly_summaries_user_created",
        "weekly_summaries",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weekly_summaries_user_created", table_name="weekly_summaries"
    )
    op.drop_table("weekly_summaries")
