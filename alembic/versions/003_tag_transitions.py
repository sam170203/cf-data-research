"""Add tag_transitions table for skill-graph discovery

Revision ID: 003
Revises: 002
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tag_transitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_tag", sa.String(64), nullable=False),
        sa.Column("target_tag", sa.String(64), nullable=False),
        sa.Column("transition_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_rating_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_source_rating", sa.Float(), nullable=True),
        sa.Column("avg_target_rating", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tag_transitions_source", "tag_transitions", ["source_tag"])
    op.create_index("ix_tag_transitions_target", "tag_transitions", ["target_tag"])


def downgrade() -> None:
    op.drop_index("ix_tag_transitions_target")
    op.drop_index("ix_tag_transitions_source")
    op.drop_table("tag_transitions")
