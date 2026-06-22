"""Initial schema: users, rating_history, contests, problems, submissions, ingestion_jobs

Revision ID: 001
Revises:
Create Date: 2026-01-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_users()
    _create_contests()
    _create_ingestion_jobs()
    _create_problems()
    _create_rating_history()
    _create_submissions()
    _create_ingestion_job_items()


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cf_handle", sa.String(64), nullable=False),
        sa.Column("current_rating", sa.Integer(), nullable=True),
        sa.Column("max_rating", sa.Integer(), nullable=True),
        sa.Column("rank", sa.String(32), nullable=True),
        sa.Column("max_rank", sa.String(32), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("organization", sa.String(256), nullable=True),
        sa.Column("contribution", sa.Integer(), nullable=True),
        sa.Column("friend_of_count", sa.Integer(), nullable=True),
        sa.Column("last_online_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("title_photo", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_cf_handle", "users", ["cf_handle"], unique=True)


def _create_contests() -> None:
    op.create_table(
        "contests",
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("prepared_by", sa.String(128), nullable=True),
        sa.Column("difficulty", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(64), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
        sa.Column("season", sa.String(32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("contest_id"),
    )


def _create_ingestion_jobs() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_job_type", "ingestion_jobs", ["job_type"])


def _create_problems() -> None:
    op.create_table(
        "problems",
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.String(8), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("solved_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["contest_id"], ["contests.contest_id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("contest_id", "index"),
    )


def _create_rating_history() -> None:
    op.create_table(
        "rating_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("contest_name", sa.String(256), nullable=False),
        sa.Column("old_rating", sa.Integer(), nullable=False),
        sa.Column("new_rating", sa.Integer(), nullable=False),
        sa.Column("rating_change", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("contest_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rating_history_user_id", "rating_history", ["user_id"])


def _create_submissions() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=True),
        sa.Column("problem_index", sa.String(8), nullable=True),
        sa.Column("problem_name", sa.String(256), nullable=True),
        sa.Column("problem_rating", sa.Integer(), nullable=True),
        sa.Column("problem_tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=True),
        sa.Column("programming_language", sa.String(64), nullable=True),
        sa.Column("submission_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])


def _create_ingestion_job_items() -> None:
    op.create_table(
        "ingestion_job_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("item_identifier", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["ingestion_jobs.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_job_items_job_id", "ingestion_job_items", ["job_id"],
    )


def downgrade() -> None:
    op.drop_table("ingestion_job_items")
    op.drop_table("submissions")
    op.drop_table("rating_history")
    op.drop_table("problems")
    op.drop_table("ingestion_jobs")
    op.drop_table("contests")
    op.drop_table("users")
