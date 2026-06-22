from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.research import (
    ExperimentTracking, PredictionRun, ResearchFinding, ResearchHypothesis,
    ResearchReport, TagTransition, UserEmbedding, UserCluster, TrajectoryMilestone,
)
from app.models.user import User
from app.models.submission import Submission

router = APIRouter(prefix="/research", tags=["research_ext"])

# Simple in-memory TTL cache for expensive endpoints
_cache: dict[str, tuple[float, Any]] = {}

def _cached(key: str, ttl: int = 3600) -> Any | None:
    entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < ttl:
        return entry[1]
    return None

def _set_cache(key: str, value: Any) -> None:
    _cache[key] = (time.monotonic(), value)


@router.get("/predictions")
async def list_predictions(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(PredictionRun).order_by(PredictionRun.created_at.desc()).limit(limit)
        )
    ).scalars().all()

    by_task: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        task = r.task_name
        by_task.setdefault(task, []).append({
            "id": r.id,
            "model_type": r.model_type,
            "task_type": r.task_type,
            "accuracy": r.accuracy,
            "f1_score": r.f1_score,
            "roc_auc": r.roc_auc,
            "mae": r.mae,
            "rmse": r.rmse,
            "r2": r.r2,
            "sample_size": r.sample_size,
            "feature_importance": r.feature_importance,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    latest_runs = {}
    for task, runs in by_task.items():
        best = None
        for r in runs:
            score = r.get("f1_score") or -r.get("mae", 0) or r.get("accuracy", 0)
            if best is None or score > (best.get("f1_score") or -best.get("mae", 0) or best.get("accuracy", 0)):
                best = r
        if best:
            best["run_count"] = len(runs)
            latest_runs[task] = best

    return {"by_task": by_task, "latest": latest_runs}


@router.get("/predictions/{task_name}")
async def get_task_predictions(
    task_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(PredictionRun)
            .where(PredictionRun.task_name == task_name)
            .order_by(PredictionRun.created_at.desc())
        )
    ).scalars().all()

    models: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        models.setdefault(r.model_type, []).append({
            "id": r.id,
            "task_type": r.task_type,
            "accuracy": r.accuracy,
            "f1_score": r.f1_score,
            "roc_auc": r.roc_auc,
            "mae": r.mae,
            "rmse": r.rmse,
            "r2": r.r2,
            "sample_size": r.sample_size,
            "feature_importance": r.feature_importance,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"task_name": task_name, "models": models, "total_runs": len(rows)}


@router.get("/experiments")
async def list_experiments(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(ExperimentTracking).order_by(ExperimentTracking.created_at.desc()).limit(limit)
        )
    ).scalars().all()

    by_task: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        by_task.setdefault(r.task_name, {}).setdefault(r.model_type, []).append({
            "id": r.id,
            "run_name": r.run_name,
            "dataset_version": r.dataset_version,
            "feature_version": r.feature_version,
            "metrics": r.metrics,
            "sample_size": r.sample_size,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {"experiments": by_task, "total": len(rows)}


@router.get("/skill-graph")
async def get_skill_graph(
    min_users: int = Query(2, ge=1),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(TagTransition)
            .where(TagTransition.user_count >= min_users)
            .order_by(TagTransition.transition_count.desc())
            .limit(limit)
        )
    ).scalars().all()

    nodes: set[str] = set()
    edges: list[dict[str, Any]] = []
    for r in rows:
        nodes.add(r.source_tag)
        nodes.add(r.target_tag)
        edges.append({
            "source": r.source_tag,
            "target": r.target_tag,
            "count": r.transition_count,
            "users": r.user_count,
            "avg_rating_gain": r.avg_rating_gain,
            "avg_source_rating": r.avg_source_rating,
            "avg_target_rating": r.avg_target_rating,
        })

    high_gain = [
        e for e in edges
        if e["avg_rating_gain"] and e["avg_rating_gain"] > 50
    ][:10]

    expert_paths = [
        e for e in edges
        if e["avg_source_rating"] and e["avg_target_rating"]
        and e["avg_source_rating"] < 1600 <= e["avg_target_rating"]
    ][:10]

    return {
        "edges": edges,
        "nodes": sorted(nodes),
        "high_gain_transitions": high_gain,
        "expert_trajectories": expert_paths,
    }


@router.get("/activity-feed")
async def get_activity_feed(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    hyps = (
        await db.execute(
            select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    for h in hyps:
        label = "hypothesis_generated"
        if h.status == "tested":
            label = "hypothesis_validated" if h.test_result == "supported" else "hypothesis_tested"
        events.append({
            "type": label,
            "description": h.question[:120],
            "detail": f"confidence={h.confidence}" if h.confidence else f"status={h.status}",
            "timestamp": h.created_at.isoformat() if h.created_at else None,
        })

    findings = (
        await db.execute(
            select(ResearchFinding).order_by(ResearchFinding.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    for f in findings:
        events.append({
            "type": "pattern_discovered",
            "description": f.title[:120],
            "detail": f"category={f.category} confidence={f.confidence_score:.2f}",
            "timestamp": f.created_at.isoformat() if f.created_at else None,
        })

    preds = (
        await db.execute(
            select(PredictionRun).order_by(PredictionRun.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    for p in preds:
        events.append({
            "type": "model_retrained",
            "description": f"{p.task_name}: {p.model_type}",
            "detail": (
                f"acc={p.accuracy} f1={p.f1_score}" if p.task_type == "classification"
                else f"mae={p.mae} r2={p.r2}"
            ),
            "timestamp": p.created_at.isoformat() if p.created_at else None,
        })

    reports = (
        await db.execute(
            select(ResearchReport).order_by(ResearchReport.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    for r in reports:
        events.append({
            "type": "report_generated",
            "description": r.title[:120],
            "detail": f"{r.findings_count} findings, {r.hypotheses_tested} tested",
            "timestamp": r.created_at.isoformat() if r.created_at else None,
        })

    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return {"events": events[:limit]}


@router.get("/hypotheses")
async def list_hypotheses(
    status: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ResearchHypothesis).order_by(ResearchHypothesis.priority.desc())
    if status:
        stmt = stmt.where(ResearchHypothesis.status == status)
    if category:
        stmt = stmt.where(ResearchHypothesis.category == category)
    rows = (await db.execute(stmt.limit(limit))).scalars().all()

    hypotheses = []
    for h in rows:
        hypotheses.append({
            "id": h.id,
            "question": h.question,
            "status": h.status,
            "priority": h.priority,
            "category": h.category,
            "confidence": h.confidence,
            "test_result": h.test_result,
            "evidence": h.evidence,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "tested_at": h.tested_at.isoformat() if h.tested_at else None,
        })
    return {"hypotheses": hypotheses, "total": len(hypotheses)}


@router.get("/embeddings")
async def list_embeddings(
    cluster: int | None = Query(None),
    limit: int = Query(200, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(UserEmbedding).order_by(UserEmbedding.current_rating.desc())
    if cluster is not None:
        stmt = stmt.where(UserEmbedding.cluster_label == cluster)
    rows = (await db.execute(stmt.limit(limit))).scalars().all()

    users = []
    for r in rows:
        users.append({
            "user_id": r.user_id,
            "handle": r.handle,
            "current_rating": r.current_rating,
            "max_rating": r.max_rating,
            "cluster_label": r.cluster_label,
            "cluster_name": r.cluster_name,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        })
    return {"users": users, "total": len(users)}


@router.get("/embeddings/{user_id}")
async def get_user_embedding(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    r = await db.execute(
        select(UserEmbedding).where(UserEmbedding.user_id == user_id)
    )
    r = r.scalar_one_or_none()
    if not r:
        return None
    return {
        "user_id": r.user_id,
        "handle": r.handle,
        "current_rating": r.current_rating,
        "max_rating": r.max_rating,
        "cluster_label": r.cluster_label,
        "cluster_name": r.cluster_name,
        "embedding": r.embedding,
        "computed_at": r.computed_at.isoformat() if r.computed_at else None,
    }


@router.get("/clusters")
async def list_clusters(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(UserCluster).order_by(UserCluster.computed_at.desc()).limit(limit)
        )
    ).scalars().all()

    runs = []
    for r in rows:
        runs.append({
            "id": r.id,
            "run_id": r.run_id,
            "algorithm": r.algorithm,
            "n_clusters": r.n_clusters,
            "metric": r.metric,
            "metric_value": r.metric_value,
            "clusters": r.clusters,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        })
    return {"runs": runs, "total": len(runs)}


@router.get("/trajectories")
async def list_trajectories(
    milestone: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Special case: compute breakthroughs on the fly from rating_history
    if milestone == "breakthrough":
        result = await db.execute(
            text("""
                SELECT rh.user_id, u.cf_handle, rh.old_rating, rh.new_rating,
                       rh.rating_change, rh.contest_time
                FROM rating_history rh
                JOIN users u ON u.id = rh.user_id
                ORDER BY rh.user_id, rh.contest_time
            """)
        )
        rows = result.all()
        by_user: dict[int, list] = {}
        for r in rows:
            by_user.setdefault(r.user_id, []).append({
                "user_id": r.user_id,
                "handle": r.cf_handle,
                "old_rating": r.old_rating,
                "new_rating": r.new_rating,
                "change": r.rating_change,
                "time": r.contest_time,
            })

        events = []
        for uid, rh_list in by_user.items():
            for i in range(1, len(rh_list)):
                gain = rh_list[i]["new_rating"] - rh_list[i - 1]["old_rating"]
                if gain >= 100:
                    events.append({
                        "user_id": uid,
                        "handle": rh_list[0]["handle"],
                        "breakthrough_gain": gain,
                        "from_rating": rh_list[i - 1]["old_rating"],
                        "to_rating": rh_list[i]["new_rating"],
                        "contest_date": rh_list[i]["time"].isoformat() if rh_list[i]["time"] else None,
                    })

        events.sort(key=lambda e: e["breakthrough_gain"], reverse=True)
        return {"milestones": {"breakthrough": events[:limit]}, "summary": {}}

    stmt = select(TrajectoryMilestone).order_by(TrajectoryMilestone.achieved_at_rating.desc())
    if milestone:
        stmt = stmt.where(TrajectoryMilestone.milestone == milestone)
    rows = (await db.execute(stmt.limit(limit))).scalars().all()

    milestones: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        milestones.setdefault(r.milestone, []).append({
            "user_id": r.user_id,
            "handle": r.handle,
            "achieved_at_rating": r.achieved_at_rating,
            "days_to_achieve": r.days_to_achieve,
            "contests_to_achieve": r.contests_to_achieve,
            "start_rating": r.start_rating,
            "first_6mo": r.first_6mo,
            "pre_breakthrough_6mo": r.pre_breakthrough_6mo,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        })

    summary = {}
    for m, users in milestones.items():
        valid = [u for u in users if u["days_to_achieve"]]
        summary[m] = {
            "total_users": len(users),
            "avg_days": round(sum(u["days_to_achieve"] for u in valid) / len(valid)) if valid else None,
            "avg_contests": round(
                sum(u["contests_to_achieve"] for u in users if u["contests_to_achieve"]) /
                max(len([u for u in users if u["contests_to_achieve"]]), 1), 1
            ),
            "avg_start_rating": round(sum(u["start_rating"] for u in users) / len(users), 1),
        }

    return {"milestones": milestones, "summary": summary}


@router.get("/trajectories/questions")
async def trajectory_questions(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    cached = _cached("trajectories_questions")
    if cached:
        return cached

    from app.research.trajectory_timelines import TrajectoryTimelineBuilder, TrajectoryQuestionAnswerer
    from app.db.session import async_sessionmaker, engine

    sf = async_sessionmaker(engine, expire_on_commit=False)
    builder = TrajectoryTimelineBuilder(sf)
    timelines = await builder.build_all_timelines()
    answerer = TrajectoryQuestionAnswerer(timelines)
    result = answerer.run_all()
    _set_cache("trajectories_questions", result)
    return result


@router.get("/expert-pathways")
async def get_expert_pathways(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cached = _cached("expert_pathways", ttl=7200)
    if cached:
        return cached

    from app.research.expert_pathways import ExpertPathwayFinder
    from app.db.session import async_sessionmaker, engine

    sf = async_sessionmaker(engine, expire_on_commit=False)
    finder = ExpertPathwayFinder(sf)
    result = await finder.find_all_pathways()
    _set_cache("expert_pathways", result)
    return result


@router.get("/breakthrough-plateau")
async def get_breakthrough_plateau(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cached = _cached("breakthrough_plateau", ttl=7200)
    if cached:
        return cached

    from app.research.breakthrough_plateau import BreakthroughPlateauAnalyzer
    from app.db.session import async_sessionmaker, engine

    sf = async_sessionmaker(engine, expire_on_commit=False)
    analyzer = BreakthroughPlateauAnalyzer(sf)
    result = await analyzer.analyze_all()
    _set_cache("breakthrough_plateau", result)
    return result


@router.get("/trajectories/summary")
async def trajectory_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(
            TrajectoryMilestone.milestone,
            func.count().label("total"),
            func.avg(TrajectoryMilestone.days_to_achieve).label("avg_days"),
            func.avg(TrajectoryMilestone.contests_to_achieve).label("avg_contests"),
            func.avg(TrajectoryMilestone.start_rating).label("avg_start_rating"),
        ).group_by(TrajectoryMilestone.milestone)
    )
    rows = result.all()
    summary = {}
    for r in rows:
        summary[r.milestone] = {
            "total_users": r.total,
            "avg_days": round(r.avg_days) if r.avg_days else None,
            "avg_contests": round(r.avg_contests, 1) if r.avg_contests else None,
            "avg_start_rating": round(r.avg_start_rating, 1) if r.avg_start_rating else None,
        }
    return summary


@router.get("/3d-dashboard")
async def get_3d_dashboard_data(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fast endpoint for the 3D dashboard — cached tag milestones + basic stats."""

    cached = _cached("3d_dashboard", ttl=7200)
    if cached:
        return cached

    from app.research.expert_pathways import ExpertPathwayFinder, MILESTONES
    from app.db.session import async_sessionmaker, engine

    sf = async_sessionmaker(engine, expire_on_commit=False)
    finder = ExpertPathwayFinder(sf)
    pathways = await finder.find_all_pathways()

    result = {
        "pathways": pathways,
        "milestones": MILESTONES,
    }
    _set_cache("3d_dashboard", result)
    return result
