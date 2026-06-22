from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.research.coordinator import ResearchCoordinator

router = APIRouter(prefix="/research", tags=["research"])

_coordinator: ResearchCoordinator | None = None


def get_coordinator() -> ResearchCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = ResearchCoordinator()
    return _coordinator


@router.get("/status")
async def research_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    coord = get_coordinator()
    loop_status = await coord.get_all_status()

    from app.models.research import (
        ResearchFinding, ResearchHypothesis, ResearchReport, SkillVector,
    )
    from sqlalchemy import func, select

    findings = (await db.execute(select(func.count()).select_from(ResearchFinding))).scalar_one() or 0
    hypotheses = (await db.execute(select(func.count()).select_from(ResearchHypothesis))).scalar_one() or 0
    reports = (await db.execute(select(func.count()).select_from(ResearchReport))).scalar_one() or 0
    vectors = (await db.execute(select(func.count()).select_from(SkillVector))).scalar_one() or 0

    return {
        "loops": loop_status,
        "totals": {
            "findings": findings,
            "hypotheses": hypotheses,
            "reports": reports,
            "skill_vectors": vectors,
        },
    }


@router.post("/start")
async def start_research() -> dict[str, str]:
    coord = get_coordinator()
    await coord.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_research() -> dict[str, str]:
    coord = get_coordinator()
    await coord.stop()
    return {"status": "stopped"}


@router.post("/run/{loop_name}")
async def run_loop(loop_name: str) -> dict[str, Any]:
    coord = get_coordinator()
    result = await coord.run_once(loop_name)
    return {"loop": loop_name, "result": result}
