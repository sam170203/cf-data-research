"""Add research tables: findings, hypotheses, reports, quality, checkpoints, skill vectors

Revision ID: 002
Revises: 001
Create Date: 2026-06-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_collection_checkpoints()
    _create_data_quality_reports()
    _create_research_findings()
    _create_research_hypotheses()
    _create_research_reports()
    _create_skill_vectors()


def _create_collection_checkpoints() -> None:
    op.create_table(
        "collection_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("loop_name", sa.String(64), nullable=False),
        sa.Column("last_handle", sa.String(64), nullable=True),
        sa.Column("last_user_id", sa.Integer(), nullable=True),
        sa.Column("offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_collection_checkpoints_loop_name",
        "collection_checkpoints",
        ["loop_name"],
    )


def _create_data_quality_reports() -> None:
    op.create_table(
        "data_quality_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("total_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_rating_histories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_contests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphan_submissions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_contests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incomplete_ingestions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_research_findings() -> None:
    op.create_table(
        "research_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("supporting_data", postgresql.JSONB(), nullable=True),
        sa.Column("source_loop", sa.String(32), nullable=False, server_default="pattern"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_findings_metric", "research_findings", ["metric"],
    )


def _create_research_hypotheses() -> None:
    op.create_table(
        "research_hypotheses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="generated"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("source_finding_id", sa.Integer(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("test_result", sa.String(16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_finding_id"], ["research_findings.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_research_reports() -> None:
    op.create_table(
        "research_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False, server_default="weekly"),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypotheses_tested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypotheses_validated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_skill_vectors() -> None:
    op.create_table(
        "skill_vectors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_skill_vectors_user_id", "skill_vectors", ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("skill_vectors")
    op.drop_table("research_reports")
    op.drop_table("research_hypotheses")
    op.drop_table("research_findings")
    op.drop_table("data_quality_reports")
    op.drop_table("collection_checkpoints")
