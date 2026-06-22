from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import ResearchFinding, ResearchHypothesis
from app.models.submission import Submission
from app.models.rating_history import RatingHistory

logger = logging.getLogger("research.hypothesis_gen")


class HypothesisGenerator:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run(self) -> int:
        async with self._sf() as session:
            findings = (
                await session.execute(
                    select(ResearchFinding).order_by(ResearchFinding.confidence_score.desc())
                )
            ).scalars().all()

            existing = (
                await session.execute(
                    select(ResearchHypothesis.question)
                )
            ).scalars().all()
            existing_questions = set(existing)

            generated = 0
            for finding in findings:
                hypotheses = self._generate_from_finding(finding)
                for h in hypotheses:
                    if h["question"] not in existing_questions:
                        hyp = ResearchHypothesis(
                            question=h["question"],
                            priority=h.get("priority", 0),
                            category=h.get("category", "general"),
                            source_finding_id=finding.id,
                            status="generated",
                        )
                        session.add(hyp)
                        generated += 1
                        existing_questions.add(h["question"])

            data_hypotheses = await self._generate_data_driven(session)
            for h in data_hypotheses:
                if h["question"] not in existing_questions:
                    hyp = ResearchHypothesis(
                        question=h["question"],
                        priority=h.get("priority", 0),
                        category=h.get("category", "general"),
                        status="generated",
                    )
                    session.add(hyp)
                    generated += 1
                    existing_questions.add(h["question"])

            await session.commit()

        logger.info("Hypothesis generation: %d new hypotheses", generated)
        return generated

    def _generate_from_finding(self, finding: ResearchFinding) -> list[dict[str, Any]]:
        title = finding.title.lower()
        desc = finding.description.lower()
        category = finding.category.lower()
        metric = finding.metric
        hypotheses: list[dict[str, Any]] = []

        if "peak" in title or "rating" in category:
            hypotheses.append({
                "question": f"What factors predict whether a user exceeds median peak rating ({metric})?",
                "priority": 7, "category": "prediction",
            })
            hypotheses.append({
                "question": f"Do users who reach peak rating earlier achieve higher eventual peaks?",
                "priority": 8, "category": "trajectory",
            })

        if "tag" in title or "mastery" in category:
            hypotheses.append({
                "question": f"Does early mastery of specific tags ({metric}) accelerate rating growth beyond other factors?",
                "priority": 9, "category": "tag_impact",
            })
            hypotheses.append({
                "question": f"Is tag breadth or tag depth more correlated with high rating?",
                "priority": 8, "category": "tag_impact",
            })
            hypotheses.append({
                "question": f"Do users who master hard tags (e.g. geometry, fft) progress faster through 1600-2000 range?",
                "priority": 9, "category": "tag_impact",
            })
            hypotheses.append({
                "question": f"What is the optimal tag learning order for fastest rating growth?",
                "priority": 8, "category": "tag_impact",
            })

        if "problem" in metric or "solve" in metric:
            hypotheses.append({
                "question": f"Is there a minimum solve threshold per rating level that predicts continued growth?",
                "priority": 7, "category": "milestone_analysis",
            })
            hypotheses.append({
                "question": f"Do users who solve above-median problems per rating level grow faster?",
                "priority": 7, "category": "milestone_analysis",
            })

        if "contest" in metric or "participation" in metric:
            hypotheses.append({
                "question": f"Is contest participation frequency a stronger predictor of growth than problem solve volume?",
                "priority": 8, "category": "consistency",
            })
            hypotheses.append({
                "question": f"Do users who participate in >10 contests before 1600 progress faster than those who participate in fewer?",
                "priority": 8, "category": "consistency",
            })
            hypotheses.append({
                "question": f"Is there a max useful contest participation rate beyond which rating gains diminish?",
                "priority": 7, "category": "optimization",
            })

        if "velocity" in metric or "growth" in metric:
            hypotheses.append({
                "question": f"Do fast-growth users (>20 pts/contest) have a different tag-solve profile?",
                "priority": 9, "category": "velocity",
            })
            hypotheses.append({
                "question": f"Is growth velocity consistent across rating tiers or does it slow down?",
                "priority": 8, "category": "velocity",
            })
            hypotheses.append({
                "question": f"Can growth velocity predict 6-month future rating?",
                "priority": 7, "category": "prediction",
            })

        if "difficulty" in title or "hierarchy" in title:
            hypotheses.append({
                "question": f"Do users who master difficult tags early have faster overall growth?",
                "priority": 9, "category": "tag_impact",
            })
            hypotheses.append({
                "question": f"Is tag difficulty hierarchy stable across rating tiers or user-dependent?",
                "priority": 7, "category": "tag_impact",
            })

        if "pacing" in metric or "consistency" in metric:
            hypotheses.append({
                "question": f"Do users with more consistent contest intervals achieve higher peak ratings?",
                "priority": 8, "category": "consistency",
            })
            hypotheses.append({
                "question": f"What is the optimal contest participation frequency for maximum rating growth?",
                "priority": 8, "category": "optimization",
            })
            hypotheses.append({
                "question": f"Do users who participate in contests less frequently compensate with more practice solves?",
                "priority": 7, "category": "consistency",
            })

        if "milestone" in category:
            hypotheses.append({
                "question": f"What distinguishes users who reach {metric.replace('problems_before_','').replace('contests_before_','')} milestone faster than the median?",
                "priority": 8, "category": "acceleration",
            })
            hypotheses.append({
                "question": f"Can we predict which users will reach the next rating milestone based on their current trajectory?",
                "priority": 7, "category": "prediction",
            })
            hypotheses.append({
                "question": f"Do solving patterns differ significantly between users who speed through 1200-1600 vs those who get stuck?",
                "priority": 9, "category": "bottleneck",
            })
            hypotheses.append({
                "question": f"What is the most common bottleneck rating range where users plateau longest?",
                "priority": 8, "category": "bottleneck",
            })

        if "predictor" in title or "correl" in title:
            hypotheses.append({
                "question": f"Does the strength of the observed correlation ({metric}) generalize across different rating tiers?",
                "priority": 8, "category": "causality",
            })
            hypotheses.append({
                "question": f"Is the relationship in '{finding.title}' causal or merely correlational?",
                "priority": 7, "category": "causality",
            })

        return hypotheses

    async def _generate_data_driven(
        self, session: AsyncSession
    ) -> list[dict[str, Any]]:
        hypotheses: list[dict[str, Any]] = []

        result = await session.execute(
            select(func.count()).select_from(
                select(Submission.user_id)
                .group_by(Submission.user_id)
                .having(func.count() > 10)
                .subquery()
            )
        )
        has_data = (result.scalar_one() or 0) > 5
        if not has_data:
            return hypotheses

        hypotheses.append({
            "question": "Do users who solve problems across more distinct tags achieve higher peak ratings?",
            "priority": 7, "category": "breadth",
        })
        hypotheses.append({
            "question": "Is there an optimal problem-solving frequency that maximizes rating growth per unit time?",
            "priority": 6, "category": "optimization",
        })
        hypotheses.append({
            "question": "Do users who participate in contests more consistently (regular intervals) grow faster than those who binge?",
            "priority": 8, "category": "consistency",
        })

        result2 = await session.execute(
            select(func.count()).select_from(
                select(RatingHistory.user_id)
                .group_by(RatingHistory.user_id)
                .having(func.max(RatingHistory.new_rating) - func.min(RatingHistory.new_rating) > 500)
                .subquery()
            )
        )
        if (result2.scalar_one() or 0) > 3:
            hypotheses.append({
                "question": "What distinguishes users who achieve 500+ rating point gains from those who plateau early?",
                "priority": 9, "category": "breakthrough",
            })

        rating_tiers = await session.execute(
            select(
                func.count(RatingHistory.user_id.distinct()).label("cnt"),
                func.max(RatingHistory.new_rating).label("max_rating"),
            )
        )
        mr = rating_tiers.scalar_one_or_none()
        if mr and mr >= 1200:
            hypotheses.append({
                "question": f"How does the solve-to-grow ratio change as users move from 1200 to 2000+?",
                "priority": 8, "category": "milestone_analysis",
            })
            hypotheses.append({
                "question": f"At which rating tier do users need the most additional solves per 100 rating gain?",
                "priority": 7, "category": "bottleneck",
            })

        sub_ratings = await session.execute(
            select(
                func.avg(Submission.problem_rating).label("avg_rating"),
                Submission.user_id,
            )
            .where(
                Submission.verdict == "OK",
                Submission.problem_rating.isnot(None),
            )
            .group_by(Submission.user_id)
        )
        sub_data = [(r.avg_rating, r.user_id) for r in sub_ratings.all() if r.avg_rating]
        if len(sub_data) >= 10:
            hypotheses.append({
                "question": f"Do users who solve above-median difficulty problems grow rating faster than those solving easier problems?",
                "priority": 8, "category": "optimization",
            })
            hypotheses.append({
                "question": f"Is there an optimal problem difficulty for practice relative to current rating?",
                "priority": 9, "category": "optimization",
            })

        return hypotheses
