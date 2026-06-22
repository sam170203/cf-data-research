"""Add experiment_tracking table

Revision ID: 004
Revises: 003
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_tracking",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_name", sa.String(128), nullable=False),
        sa.Column("dataset_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("feature_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("task_name", sa.String(64), nullable=False),
        sa.Column("task_type", sa.String(16), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("feature_importance", postgresql.JSONB(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("experiment_tracking")
