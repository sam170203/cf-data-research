"""Autonomous Research System - Knowledge Extraction Loop

Collect → Embed → Cluster → Discover Trajectories → Research →
Predict → Analyze Failures → Generate Hypotheses → Repeat.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from sqlalchemy import func, select

from app.db.session import engine
from app.models.contest import Contest
from app.models.problem import Problem
from app.models.research import ResearchFinding, ResearchHypothesis, ResearchReport, PredictionRun
from app.models.submission import Submission
from app.models.user import User
from app.research.coordinator import ResearchCoordinator

logger = logging.getLogger("autonomous_research")

BATCH_SIZE = 20
TARGETS = {
    "users": 1000,
    "submissions": 3_000_000,
    "findings": 150,
    "hypotheses": 50,
    "tested": 30,
}


async def get_counts(coord: ResearchCoordinator) -> dict[str, int]:
    async with coord._session_factory() as session:
        users = (await session.execute(select(func.count()).select_from(User))).scalar_one() or 0
        subs = (await session.execute(select(func.count()).select_from(Submission))).scalar_one() or 0
        findings = (await session.execute(select(func.count()).select_from(ResearchFinding))).scalar_one() or 0
        hyps = (await session.execute(select(func.count()).select_from(ResearchHypothesis))).scalar_one() or 0
        tested = (await session.execute(
            select(func.count()).select_from(ResearchHypothesis).where(
                ResearchHypothesis.status == "tested"
            )
        )).scalar_one() or 0
        validated = (await session.execute(
            select(func.count()).select_from(ResearchHypothesis).where(
                ResearchHypothesis.test_result == "supported"
            )
        )).scalar_one() or 0
        prediction_runs = (await session.execute(select(func.count()).select_from(PredictionRun))).scalar_one() or 0
        contests = (await session.execute(select(func.count()).select_from(Contest))).scalar_one() or 0
        problems = (await session.execute(select(func.count()).select_from(Problem))).scalar_one() or 0
        reports = (await session.execute(select(func.count()).select_from(ResearchReport))).scalar_one() or 0

    return {
        "users": users,
        "submissions": subs,
        "findings": findings,
        "hypotheses": hyps,
        "tested": tested,
        "validated": validated,
        "prediction_runs": prediction_runs,
        "contests": contests,
        "problems": problems,
        "reports": reports,
    }


def format_status(c: dict[str, int]) -> str:
    parts = [
        f"👤{c['users']}/{TARGETS['users']}",
        f"📝{c['submissions']}",
        f"💡{c['findings']}/{TARGETS['findings']}",
        f"❓{c['hypotheses']}/{TARGETS['hypotheses']}",
        f"✅{c['tested']}/{TARGETS['tested']}",
        f"🔬{c['validated']}v",
        f"🤖{c['prediction_runs']}pr",
    ]
    return " | ".join(parts)


async def run_phases(coord: ResearchCoordinator, phases: list[str]) -> None:
    for phase in phases:
        try:
            await coord.run_once(phase)
        except BaseException as e:
            logger.warning("Phase %s failed (non-fatal): %s", phase, e)


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    coord = ResearchCoordinator()
    iteration = 0

    research_phases = [
        "data_quality", "pattern_discovery",
        "hypothesis_generation", "hypothesis_testing",
        "skill_vectors", "skill_graph", "report_generation",
    ]

    extraction_phases = [
        "embeddings", "clustering", "trajectories",
    ]

    logger.info("=== INITIAL KNOWLEDGE EXTRACTION PASS ===")
    await run_phases(coord, research_phases)
    await run_phases(coord, extraction_phases)

    c = await get_counts(coord)
    logger.info("Initial state: %s", format_status(c))

    while True:
        iteration += 1
        logger.info("=== Research Loop Iteration %d ===", iteration)
        c = await get_counts(coord)
        logger.info("Status: %s", format_status(c))

        # Phase 1: Collect data (if below target)
        if c["users"] < TARGETS["users"]:
            remaining = TARGETS["users"] - c["users"]
            batch = min(BATCH_SIZE, remaining)
            logger.info("📡 Phase: DATA COLLECTION — collecting %d users (have %d)", batch, c["users"])
            await coord.run_once("data_acquisition")
            c2 = await get_counts(coord)
            new_users = c2["users"] - c["users"]
            new_subs = c2["submissions"] - c["submissions"]
            logger.info("📡 After collection: +%d users, +%d submissions", new_users, new_subs)
            c = await get_counts(coord)
        else:
            logger.info("📡 Phase: DATASET TARGET MET (%d users) — maintaining", c["users"])

        # Phase 2: User Embeddings
        logger.info("📊 Phase: USER EMBEDDINGS")
        await coord.run_once("embeddings")

        # Phase 3: Clustering
        logger.info("🔮 Phase: CLUSTERING")
        await coord.run_once("clustering")

        # Phase 4: Trajectory Discovery
        logger.info("🛤️  Phase: TRAJECTORY DISCOVERY")
        await coord.run_once("trajectories")

        # Phase 5: Research (patterns, skill graph, hypotheses)
        logger.info("📊 Phase: RESEARCH — patterns, skill graph, hypotheses")
        await run_phases(coord, research_phases)

        # Phase 6: Predictive modeling
        logger.info("🤖 Phase: PREDICTIVE MODELING")
        await coord.run_once("prediction")

        # Phase 7: Failure analysis
        logger.info("🔬 Phase: FAILURE ANALYSIS")
        await coord.run_once("failure_analysis")

        # Phase 8: Hypothesis generation from failures
        logger.info("❓ Phase: HYPOTHESIS GENERATION")
        await coord.run_once("hypothesis_generation")

        # Phase 9: Test new hypotheses
        logger.info("🧪 Phase: HYPOTHESIS TESTING")
        await coord.run_once("hypothesis_testing")

        # Phase 10: Report
        logger.info("📋 Phase: REPORT GENERATION")
        await coord.run_once("report_generation")

        c = await get_counts(coord)
        logger.info("📊 Post-cycle: %s", format_status(c))
        logger.info("=" * 60)
        logger.info("CYCLE %d COMPLETE — sleeping before next iteration", iteration)
        logger.info("=" * 60)

        await asyncio.sleep(300)

    await engine.dispose()
    logger.info("Autonomous research complete.")


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Research interrupted by user")
    except Exception as e:
        logger.exception("Research failed: %s", e)


if __name__ == "__main__":
    main()
