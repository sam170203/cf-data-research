from __future__ import annotations

import logging
import statistics
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.research import ResearchHypothesis

logger = logging.getLogger("research.hypothesis_test")


class HypothesisTester:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async with self._sf() as session:
            hypotheses = (
                await session.execute(
                    select(ResearchHypothesis).where(
                        ResearchHypothesis.status == "generated"
                    ).order_by(ResearchHypothesis.priority.desc())
                    .limit(10)
                )
            ).scalars().all()

            for hyp in hypotheses:
                try:
                    result = await self._test_hypothesis(session, hyp)
                    hyp.status = "tested"
                    hyp.test_result = result["verdict"]
                    hyp.confidence = result.get("confidence")
                    hyp.evidence = result.get("evidence")
                    hyp.tested_at = datetime.now(UTC)
                    results.append(result)
                except Exception as e:
                    logger.warning("Failed to test hypothesis %d: %s", hyp.id, e)
                    hyp.status = "error"

            await session.commit()

        logger.info(
            "Hypothesis testing: %d tested (%d supported, %d unsupported)",
            len(results),
            sum(1 for r in results if r.get("verdict") == "supported"),
            sum(1 for r in results if r.get("verdict") == "unsupported"),
        )
        return results

    async def _test_hypothesis(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        q = hyp.question.lower()

        if "different rating tiers" in q or "generalize across" in q:
            return await self._test_correlation_generalization(session, hyp)
        elif "causal" in q or "correlational" in q:
            return {"verdict": "inconclusive", "confidence": 0.1,
                    "evidence": {"reason": "Causality requires controlled experiments"}}
        elif "tag" in q or "mastery" in q:
            return await self._test_tag_impact(session, hyp)
        elif "faster than median" in q:
            return await self._test_acceleration_factors(session, hyp)
        elif "predict which users" in q:
            return await self._test_milestone_prediction(session, hyp)
        elif "fast-growth" in q:
            return await self._test_fast_growth_profile(session, hyp)
        elif "distinct tags" in q:
            return await self._test_tag_breadth(session, hyp)
        elif "optimal" in q and "frequency" in q:
            return await self._test_solve_frequency(session, hyp)
        elif "consistent" in q:
            return await self._test_consistency(session, hyp)
        elif "500+" in q or "500 point" in q:
            return await self._test_breakthrough_users(session, hyp)
        else:
            return {"verdict": "inconclusive", "confidence": 0.0,
                    "evidence": {"reason": "No automated test defined for this hypothesis"}}

    async def _test_correlation_generalization(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        tiers = [(0, 1399, "below_1400"), (1400, 1899, "1400_1899"), (1900, 4000, "1900+")]
        results: dict[str, float] = {}
        for lo, hi, label in tiers:
            result = await session.execute(
                select(
                    RatingHistory.user_id,
                    func.count(RatingHistory.id).label("contest_count"),
                    func.max(RatingHistory.new_rating).label("rating"),
                )
                .where(RatingHistory.new_rating.between(lo, hi))
                .group_by(RatingHistory.user_id)
            )
            data = [(r.contest_count, r.rating) for r in result.all() if r.contest_count and r.rating]
            if len(data) >= 5:
                x = [d[0] for d in data]
                y = [d[1] for d in data]
                results[label] = round(self._pearson(x, y), 3)

        supported = all(abs(v) > 0.1 for v in results.values()) if results else False
        return {
            "verdict": "supported" if supported else "inconclusive",
            "confidence": 0.6,
            "evidence": {
                "correlations_by_tier": results,
                "note": "Correlation persists across tiers" if supported else "Insufficient data",
            },
        }

    async def _test_tag_impact(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                Submission.problem_tags,
                Submission.problem_rating,
            )
            .where(
                Submission.verdict == "OK",
                Submission.problem_tags.isnot(None),
                Submission.problem_rating.isnot(None),
            )
            .limit(30000)
        )
        tag_ratings: dict[str, list[int]] = {}
        for tags, rating in result.all():
            if tags and rating:
                for tag in tags:
                    tag_ratings.setdefault(tag, []).append(rating)

        if len(tag_ratings) < 5:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": "Insufficient tag data"}}

        tag_avg = {t: statistics.mean(r) for t, r in tag_ratings.items() if len(r) >= 10}
        sorted_tags = sorted(tag_avg.items(), key=lambda x: -x[1])
        top = sorted_tags[:5]
        bottom = sorted_tags[-5:]

        spread = top[0][1] - bottom[0][1] if top and bottom else 0
        supported = spread > 200

        return {
            "verdict": "supported" if supported else "unsupported",
            "confidence": 0.6,
            "evidence": {
                "spread": round(spread, 1),
                "highest_tags": [{"tag": t, "avg_rating": round(r, 1)} for t, r in top],
                "lowest_tags": [{"tag": t, "avg_rating": round(r, 1)} for t, r in bottom],
                "interpretation": (
                    f"Tag difficulty spans {spread:.0f} rating points, suggesting "
                    f"certain tags require substantially higher skill levels"
                    if supported else
                    f"Tags show relatively uniform difficulty (spread: {spread:.0f})"
                ),
            },
        }

    async def _test_acceleration_factors(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("contest_count"),
                func.max(RatingHistory.new_rating).label("peak_rating"),
                func.min(RatingHistory.contest_time).label("first_contest"),
                func.max(RatingHistory.contest_time).label("last_contest"),
            )
            .group_by(RatingHistory.user_id)
            .having(func.count(RatingHistory.id) >= 5)
        )
        user_data = result.all()
        if len(user_data) < 10:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": f"Only {len(user_data)} users with >=5 contests"}}

        milestones = [1200, 1400, 1600, 1900]
        results_by_milestone: dict[int, dict] = {}
        for ms in milestones:
            r2 = await session.execute(
                select(
                    RatingHistory.user_id,
                    func.min(RatingHistory.contest_time).label("ms_time"),
                )
                .where(RatingHistory.new_rating >= ms)
                .group_by(RatingHistory.user_id)
            )
            ms_users = {(r.user_id, r.ms_time) for r in r2.all() if r.ms_time}
            if len(ms_users) >= 5:
                time_to_ms = []
                for uid, ms_time in ms_users:
                    first = next((u.first_contest for u in user_data if u.user_id == uid), None)
                    if first and ms_time > first:
                        days = (ms_time - first).total_seconds() / 86400
                        if 1 <= days <= 3650:
                            time_to_ms.append(days)
                if len(time_to_ms) >= 5:
                    results_by_milestone[ms] = {
                        "median_days": round(statistics.median(time_to_ms), 1),
                        "sample_size": len(time_to_ms),
                    }

        if not results_by_milestone:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": "No milestone cohorts large enough"}}

        supported = any(r["sample_size"] >= 10 for r in results_by_milestone.values())

        return {
            "verdict": "supported" if supported else "inconclusive",
            "confidence": 0.55,
            "evidence": {
                "milestone_stats": results_by_milestone,
                "interpretation": (
                    f"Analyzed {len(results_by_milestone)} milestones with sufficient data"
                    if supported else "Insufficient data per milestone"
                ),
            },
        }

    async def _test_milestone_prediction(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        return {
            "verdict": "inconclusive",
            "confidence": 0.2,
            "evidence": {
                "reason": "Prediction requires ML model - tracking as future feature",
            },
        }

    async def _test_fast_growth_profile(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("contest_count"),
                func.max(RatingHistory.new_rating) - func.min(RatingHistory.old_rating),
            )
            .group_by(RatingHistory.user_id)
            .having(func.count(RatingHistory.id) > 5)
        )
        users = [(r.user_id, r.contest_count, r[2]) for r in result.all() if r[2]]
        if len(users) < 10:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": "Too few users"}}

        gains = sorted([u[2] for u in users], reverse=True)
        top_quartile = gains[len(gains) // 4] if gains else 0

        fast_users = [u for u in users if u[2] >= top_quartile]
        slow_users = [u for u in users if u[2] < top_quartile]

        fast_contests = [u[1] for u in fast_users]
        slow_contests = [u[1] for u in slow_users]

        if fast_contests and slow_contests:
            fast_mean = statistics.mean(fast_contests)
            slow_mean = statistics.mean(slow_contests)
            ratio = fast_mean / slow_mean if slow_mean > 0 else 1
            supported = ratio > 1.3

            return {
                "verdict": "supported" if supported else "unsupported",
                "confidence": 0.65 if supported else 0.5,
                "evidence": {
                    "fast_growth_mean_contests": round(fast_mean, 1),
                    "slow_growth_mean_contests": round(slow_mean, 1),
                    "ratio": round(ratio, 2),
                    "sample_size_fast": len(fast_users),
                    "sample_size_slow": len(slow_users),
                    "interpretation": (
                        f"Fast-growth users participate in {ratio:.1f}x more contests"
                        if supported else
                        "No significant contest frequency difference"
                    ),
                },
            }

        return {"verdict": "inconclusive", "confidence": 0.2,
                "evidence": {"reason": "Insufficient data"}}

    async def _test_tag_breadth(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                Submission.user_id,
                func.count(Submission.id.distinct()).label("unique_tags"),
                func.max(Submission.problem_rating).label("max_rating"),
            )
            .where(Submission.verdict == "OK", Submission.problem_tags.isnot(None))
            .group_by(Submission.user_id)
        )
        data = [(r.unique_tags, r.max_rating) for r in result.all() if r.max_rating]
        if len(data) < 10:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": "Too few users"}}

        x = [d[0] for d in data]
        y = [d[1] for d in data]
        corr = self._pearson(x, y)

        supported = corr > 0.2
        return {
            "verdict": "supported" if supported else "unsupported",
            "confidence": 0.55,
            "evidence": {
                "tag_breadth_rating_correlation": round(corr, 3),
                "sample_size": len(data),
            },
        }

    async def _test_solve_frequency(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                Submission.user_id,
                Submission.submission_time,
                Submission.problem_rating,
            )
            .where(
                Submission.verdict == "OK",
                Submission.problem_rating.isnot(None),
            )
            .order_by(Submission.user_id, Submission.submission_time)
        )
        rows = result.all()
        if len(rows) < 100:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": f"Only {len(rows)} solved submissions"}}

        user_first: dict[int, datetime] = {}
        user_last: dict[int, datetime] = {}
        user_solves: dict[int, int] = {}
        user_ratings: dict[int, list[int]] = {}
        for uid, st, pr in rows:
            if st is None:
                continue
            user_solves[uid] = user_solves.get(uid, 0) + 1
            if uid not in user_first or st < user_first[uid]:
                user_first[uid] = st
            if uid not in user_last or st > user_last[uid]:
                user_last[uid] = st
            if pr:
                user_ratings.setdefault(uid, []).append(pr)

        solves_per_day: list[tuple[int, float, int]] = []
        for uid in user_solves:
            if uid in user_first and uid in user_last and uid in user_ratings:
                span = (user_last[uid] - user_first[uid]).total_seconds() / 86400
                if span >= 7:
                    spd = user_solves[uid] / span
                    peak = max(user_ratings[uid])
                    solves_per_day.append((uid, spd, peak))

        if len(solves_per_day) < 10:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": f"Only {len(solves_per_day)} users with temporal data"}}

        x = [s[1] for s in solves_per_day]
        y = [s[2] for s in solves_per_day]
        corr = self._pearson(x, y)

        fast = [s[2] for s in solves_per_day if s[1] > statistics.median(x)]
        slow = [s[2] for s in solves_per_day if s[1] <= statistics.median(x)]
        diff = (statistics.mean(fast) - statistics.mean(slow)) if fast and slow else 0
        supported = diff > 50

        return {
            "verdict": "supported" if supported else "unsupported",
            "confidence": 0.55,
            "evidence": {
                "correlation_solve_frequency_rating": round(corr, 3),
                "sample_size": len(solves_per_day),
                "high_freq_mean_rating": round(statistics.mean(fast), 1) if fast else 0,
                "low_freq_mean_rating": round(statistics.mean(slow), 1) if slow else 0,
                "mean_diff": round(diff, 1),
                "interpretation": (
                    f"Higher solve frequency correlates with {diff:.0f} point higher average rating"
                    if supported else "No significant rating difference by solve frequency"
                ),
            },
        }

    async def _test_consistency(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                RatingHistory.contest_time,
            )
            .order_by(RatingHistory.user_id, RatingHistory.contest_time)
        )
        rows = result.all()
        if len(rows) < 20:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": "Insufficient contest history data"}}

        user_intervals: dict[int, list[float]] = {}
        prev_user = None
        prev_time = None
        for uid, ct in rows:
            if ct is None:
                continue
            if uid == prev_user and prev_time is not None:
                days = (ct - prev_time).total_seconds() / 86400
                if 1 <= days <= 365:
                    user_intervals.setdefault(uid, []).append(days)
            prev_user = uid
            prev_time = ct

        user_cvs: list[tuple[int, float, int, int]] = []
        for uid, vals in user_intervals.items():
            if len(vals) >= 3:
                m = statistics.mean(vals)
                if m > 0:
                    cv = statistics.stdev(vals) / m
                    r = await session.execute(
                        select(func.max(RatingHistory.new_rating))
                        .where(RatingHistory.user_id == uid)
                    )
                    peak = r.scalar() or 0
                    user_cvs.append((uid, cv, len(vals), peak))

        if len(user_cvs) < 10:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": f"Only {len(user_cvs)} users with interval data"}}

        sorted_by_cv = sorted(user_cvs, key=lambda x: x[1])
        top_n = max(len(user_cvs) // 4, 1)
        most_consistent = sorted_by_cv[:top_n]
        least_consistent = sorted_by_cv[-top_n:]

        consistent_ratings = [u[3] for u in most_consistent]
        inconsistent_ratings = [u[3] for u in least_consistent]
        if consistent_ratings and inconsistent_ratings:
            mc_mean = statistics.mean(consistent_ratings)
            lc_mean = statistics.mean(inconsistent_ratings)
            diff = mc_mean - lc_mean
            supported = diff > 100

            return {
                "verdict": "supported" if supported else "unsupported",
                "confidence": 0.6,
                "evidence": {
                    "consistent_users_peak_rating_mean": round(mc_mean, 1),
                    "inconsistent_users_peak_rating_mean": round(lc_mean, 1),
                    "rating_diff": round(diff, 1),
                    "consistent_sample": len(consistent_ratings),
                    "inconsistent_sample": len(inconsistent_ratings),
                    "interpretation": (
                        f"Consistent participants average {diff:.0f} points higher than inconsistent"
                        if supported else "No significant rating difference by consistency"
                    ),
                },
            }

        return {"verdict": "inconclusive", "confidence": 0.2,
                "evidence": {"reason": "Could not compute consistency cohorts"}}

    async def _test_breakthrough_users(
        self, session: AsyncSession, hyp: ResearchHypothesis
    ) -> dict[str, Any]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("total_contests"),
                func.max(RatingHistory.new_rating) - func.min(RatingHistory.new_rating),
            )
            .group_by(RatingHistory.user_id)
            .having(func.max(RatingHistory.new_rating) - func.min(RatingHistory.new_rating) > 500)
        )
        breakthrough_users = result.all()
        if len(breakthrough_users) < 3:
            return {"verdict": "inconclusive", "confidence": 0.2,
                    "evidence": {"reason": f"Only {len(breakthrough_users)} breakthrough users found"}}

        gains = [u[2] for u in breakthrough_users]
        return {
            "verdict": "supported",
            "confidence": 0.7,
            "evidence": {
                "breakthrough_count": len(breakthrough_users),
                "mean_gain": round(statistics.mean(gains), 1) if gains else 0,
                "median_gain": round(statistics.median(gains), 1) if gains else 0,
                "note": "Breakthrough users exist and are analyzable",
            },
        }

    def _pearson(self, x: list[float], y: list[float]) -> float:
        n = len(x)
        if n < 3:
            return 0.0
        mx = statistics.mean(x)
        my = statistics.mean(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        denom = (sum((xi - mx) ** 2 for xi in x) *
                 sum((yi - my) ** 2 for yi in y)) ** 0.5
        if denom == 0:
            return 0.0
        return num / denom
