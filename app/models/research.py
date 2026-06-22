from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionCheckpoint(Base):
    __tablename__ = "collection_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loop_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    total_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_rating_histories: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_contests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orphan_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_contests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incomplete_ingestions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supporting_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_loop: Mapped[str] = mapped_column(String(32), nullable=False, default="pattern")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchHypothesis(Base):
    __tablename__ = "research_hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="generated"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    source_finding_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("research_findings.id", ondelete="SET NULL"), nullable=True
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    test_result: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, default="weekly")
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypotheses_tested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypotheses_validated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SkillVector(Base):
    __tablename__ = "skill_vectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skills: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TagTransition(Base):
    __tablename__ = "tag_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_source_rating: Mapped[float] = mapped_column(Float, nullable=True)
    avg_target_rating: Mapped[float] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExperimentTracking(Base):
    __tablename__ = "experiment_tracking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(16), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_importance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    r2: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_importance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    shap_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    failure_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserEmbedding(Base):
    __tablename__ = "user_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    handle: Mapped[str] = mapped_column(String(64), nullable=False)
    current_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    cluster_label: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cluster_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserCluster(Base):
    __tablename__ = "user_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    n_clusters: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String(16), nullable=False, default="silhouette")
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    clusters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TrajectoryMilestone(Base):
    __tablename__ = "trajectory_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    milestone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    handle: Mapped[str] = mapped_column(String(64), nullable=False)
    achieved_at_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    days_to_achieve: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contests_to_achieve: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_6mo: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    pre_breakthrough_6mo: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
