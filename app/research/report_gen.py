from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import (
    DataQualityReport,
    ResearchFinding,
    ResearchHypothesis,
    ResearchReport,
)

logger = logging.getLogger("research.report_gen")


class ReportGenerator:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run(self) -> dict[str, Any]:
        async with self._sf() as session:
            latest_quality = (
                await session.execute(
                    select(DataQualityReport).order_by(DataQualityReport.created_at.desc()).limit(1)
                )
            ).scalar_one_or_none()

            new_findings = (
                await session.execute(
                    select(ResearchFinding).order_by(ResearchFinding.created_at.desc()).limit(10)
                )
            ).scalars().all()

            hypotheses = (
                await session.execute(
                    select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc())
                )
            ).scalars().all()

            latest_hypothesis = (
                await session.execute(
                    select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc()).limit(1)
                )
            ).scalar_one_or_none()

            total_findings = (
                await session.execute(select(func.count()).select_from(ResearchFinding))
            ).scalar_one() or 0
            total_hypotheses = (
                await session.execute(select(func.count()).select_from(ResearchHypothesis))
            ).scalar_one() or 0
            tested = sum(1 for h in hypotheses if h.status == "tested")
            validated = sum(1 for h in hypotheses if h.test_result == "supported")

            if not new_findings and not latest_quality:
                logger.info("No data for report generation")
                return {"id": None, "note": "insufficient data"}

            quality_line = (
                f"Dataset Quality Score: {latest_quality.quality_score:.1f}%"
                if latest_quality else "No quality assessment yet"
            )

            summary_parts = [quality_line]

            if new_findings:
                summary_parts.append(f"\n\n## New Findings ({len(new_findings)})")
                for f in new_findings[:5]:
                    summary_parts.append(
                        f"- {f.title} (confidence: {f.confidence_score:.0%})"
                    )
                if len(new_findings) > 5:
                    summary_parts.append(f"- ... and {len(new_findings) - 5} more")

            tested_h = [h for h in hypotheses if h.test_result]
            if tested_h:
                summary_parts.append(f"\n\n## Tested Hypotheses ({len(tested_h)})")
                supported = [h for h in tested_h if h.test_result == "supported"]
                unsupported = [h for h in tested_h if h.test_result == "unsupported"]
                if supported:
                    summary_parts.append("Supported:")
                    for h in supported[:3]:
                        summary_parts.append(f"- {h.question[:120]}...")
                if unsupported:
                    summary_parts.append("Unsupported:")
                    for h in unsupported[:3]:
                        summary_parts.append(f"- {h.question[:120]}...")

            report_title = f"Research Report #{total_findings} - {len(new_findings)} new findings"

            report = ResearchReport(
                title=report_title,
                summary="\n".join(summary_parts),
                report_type="auto",
                findings_count=len(new_findings),
                hypotheses_tested=tested,
                hypotheses_validated=validated,
                content={
                    "quality": {
                        "score": latest_quality.quality_score if latest_quality else None,
                        "details": latest_quality.details if latest_quality else None,
                    },
                    "findings": [
                        {"title": f.title, "description": f.description[:200],
                         "confidence": f.confidence_score, "metric": f.metric}
                        for f in new_findings
                    ],
                    "hypotheses": {
                        "total": total_hypotheses,
                        "tested": tested,
                        "validated": validated,
                        "recent": [
                            {"question": h.question[:200], "result": h.test_result,
                             "confidence": h.confidence}
                            for h in hypotheses[:5]
                        ],
                    },
                },
            )
            session.add(report)
            await session.commit()
            await session.refresh(report)

        logger.info(
            "Report generated: id=%d, findings=%d, tested=%d, validated=%d",
            report.id, len(new_findings), tested, validated,
        )
        return {"id": report.id, "title": report_title}
