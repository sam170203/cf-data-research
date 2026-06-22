from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.contest import Contest
from app.models.ingestion import IngestionJob
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.research import (
    DataQualityReport,
    ResearchFinding,
    ResearchHypothesis,
    ResearchReport,
    SkillVector,
)
from app.models.submission import Submission
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    async def count(model: type[Any]) -> int:
        r = await db.execute(select(func.count()).select_from(model))
        return r.scalar_one() or 0

    users = await count(User)
    subs = await count(Submission)
    ratings = await count(RatingHistory)
    contests = await count(Contest)
    problems = await count(Problem)
    findings = await count(ResearchFinding)
    hypotheses = await count(ResearchHypothesis)
    reports = await count(ResearchReport)
    skill_vectors = await count(SkillVector)

    tested = (
        await db.execute(
            select(func.count()).select_from(ResearchHypothesis).where(
                ResearchHypothesis.status == "tested"
            )
        )
    ).scalar_one() or 0

    validated = (
        await db.execute(
            select(func.count()).select_from(ResearchHypothesis).where(
                ResearchHypothesis.test_result == "supported"
            )
        )
    ).scalar_one() or 0

    latest_quality = (
        await db.execute(
            select(DataQualityReport).order_by(DataQualityReport.created_at.desc())
        )
    ).scalars().first()

    latest_report = (
        await db.execute(
            select(ResearchReport).order_by(ResearchReport.created_at.desc())
        )
    ).scalars().first()

    recent_findings = (
        await db.execute(
            select(ResearchFinding).order_by(ResearchFinding.created_at.desc()).limit(5)
        )
    ).scalars().all()

    pending_hypotheses = (
        await db.execute(
            select(func.count()).select_from(ResearchHypothesis).where(
                ResearchHypothesis.status == "generated"
            )
        )
    ).scalar_one() or 0

    return {
        "data_collection": {
            "users": users,
            "submissions": subs,
            "rating_histories": ratings,
            "contests": contests,
            "problems": problems,
        },
        "research_progress": {
            "findings": findings,
            "hypotheses": hypotheses,
            "tested": tested,
            "validated": validated,
            "pending_tests": pending_hypotheses,
            "reports": reports,
            "skill_vectors": skill_vectors,
        },
        "quality": {
            "latest_score": latest_quality.quality_score if latest_quality else None,
            "last_checked": latest_quality.created_at.isoformat() if latest_quality else None,
        },
        "latest_report": {
            "id": latest_report.id if latest_report else None,
            "title": latest_report.title if latest_report else None,
            "created_at": latest_report.created_at.isoformat() if latest_report else None,
        },
        "recent_findings": [
            {
                "title": f.title,
                "metric": f.metric,
                "confidence": f.confidence_score,
                "category": f.category,
                "created_at": f.created_at.isoformat(),
            }
            for f in recent_findings
        ],
    }


@router.get("/findings")
async def list_findings(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    findings = (
        await db.execute(
            select(ResearchFinding)
            .order_by(ResearchFinding.confidence_score.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "description": f.description[:200],
            "metric": f.metric,
            "category": f.category,
            "confidence": f.confidence_score,
            "source_loop": f.source_loop,
            "created_at": f.created_at.isoformat(),
        }
        for f in findings
    ]


@router.get("/hypotheses")
async def list_hypotheses(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    hypotheses = (
        await db.execute(
            select(ResearchHypothesis)
            .order_by(ResearchHypothesis.priority.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": h.id,
            "question": h.question[:200],
            "status": h.status,
            "priority": h.priority,
            "category": h.category,
            "test_result": h.test_result,
            "confidence": h.confidence,
            "created_at": h.created_at.isoformat(),
            "tested_at": h.tested_at.isoformat() if h.tested_at else None,
        }
        for h in hypotheses
    ]


@router.get("/reports")
async def list_reports(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    reports = (
        await db.execute(
            select(ResearchReport)
            .order_by(ResearchReport.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary[:300],
            "report_type": r.report_type,
            "findings_count": r.findings_count,
            "hypotheses_tested": r.hypotheses_tested,
            "hypotheses_validated": r.hypotheses_validated,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    report = await db.get(ResearchReport, report_id)
    if not report:
        return None
    return {
        "id": report.id,
        "title": report.title,
        "summary": report.summary,
        "report_type": report.report_type,
        "findings_count": report.findings_count,
        "hypotheses_tested": report.hypotheses_tested,
        "hypotheses_validated": report.hypotheses_validated,
        "content": report.content,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/quality-history")
async def quality_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    reports = (
        await db.execute(
            select(DataQualityReport)
            .order_by(DataQualityReport.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "quality_score": r.quality_score,
            "total_users": r.total_users,
            "missing_rating_histories": r.missing_rating_histories,
            "orphan_submissions": r.orphan_submissions,
            "duplicate_users": r.duplicate_users,
            "details": r.details,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]
