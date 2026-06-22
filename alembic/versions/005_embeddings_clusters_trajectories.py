"""Add user_embeddings, user_clusters, trajectory_milestones tables

Revision ID: 005
Revises: 004
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("handle", sa.String(64), nullable=False),
        sa.Column("current_rating", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_rating", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", postgresql.JSONB(), nullable=False),
        sa.Column("cluster_label", sa.Integer(), nullable=True),
        sa.Column("cluster_name", sa.String(64), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_embeddings_cluster_label", "user_embeddings", ["cluster_label"])

    op.create_table(
        "user_clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(32), nullable=False, index=True),
        sa.Column("algorithm", sa.String(16), nullable=False),
        sa.Column("n_clusters", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(16), nullable=False, server_default="silhouette"),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("clusters", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trajectory_milestones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("milestone", sa.String(32), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("handle", sa.String(64), nullable=False),
        sa.Column("achieved_at_rating", sa.Integer(), nullable=False),
        sa.Column("days_to_achieve", sa.Integer(), nullable=True),
        sa.Column("contests_to_achieve", sa.Integer(), nullable=True),
        sa.Column("start_rating", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_6mo", postgresql.JSONB(), nullable=True),
        sa.Column("pre_breakthrough_6mo", postgresql.JSONB(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("trajectory_milestones")
    op.drop_table("user_clusters")
    op.drop_table("user_embeddings")
