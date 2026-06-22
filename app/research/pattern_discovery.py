from __future__ import annotations

import logging
import statistics
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.rating_history import RatingHistory
from app.models.research import ResearchFinding, TagTransition
from app.models.submission import Submission
from app.models.user import User

from app.research.skill_graph import SkillGraphBuilder

logger = logging.getLogger("research.pattern_discovery")


class PatternDiscoveryRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory
        self._findings: list[dict[str, Any]] = []

    async def run(self) -> list[dict[str, Any]]:
        # Build skill graph first
        await SkillGraphBuilder(self._sf).run()

        self._findings = []
        async with self._sf() as session:
            existing_titles = set(
                (await session.execute(
                    select(ResearchFinding.title)
                )).scalars().all()
            )

            await self._analyze_rating_progression(session)
            await self._analyze_tag_mastery(session)
            await self._analyze_problems_to_milestone(session)
            await self._analyze_contests_to_milestone(session)
            await self._analyze_growth_velocity(session)
            await self._analyze_growth_predictors(session)
            await self._analyze_tag_rating_correlation(session)
            await self._analyze_contest_pacing(session)
            await self._analyze_skill_graph(session)

            inserted = 0
            for f in self._findings:
                if f["title"] in existing_titles:
                    continue
                existing_titles.add(f["title"])
                finding = ResearchFinding(
                    title=f["title"],
                    description=f["description"],
                    metric=f["metric"],
                    category=f.get("category", "general"),
                    confidence_score=f.get("confidence", 0.0),
                    supporting_data=f.get("data"),
                    source_loop="pattern",
                )
                session.add(finding)
                inserted += 1
            await session.commit()

        logger.info("Pattern discovery: %d stored (%d new)", len(self._findings), inserted)
        return self._findings

    async def _analyze_rating_progression(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.min(RatingHistory.contest_time).label("first_contest"),
                func.max(RatingHistory.contest_time).label("last_contest"),
                func.min(RatingHistory.new_rating).label("min_rating"),
                func.max(RatingHistory.new_rating).label("max_rating"),
                func.count(RatingHistory.id).label("total_contests"),
            ).group_by(RatingHistory.user_id)
        )
        rows = result.all()
        if len(rows) < 5:
            return

        max_ratings = [r.max_rating for r in rows if r.max_rating]
        if max_ratings:
            median_max = statistics.median(max_ratings)
            mean_max = statistics.mean(max_ratings)
            self._findings.append({
                "title": f"Median peak rating across {len(rows)} users is {median_max:.0f}",
                "description": (
                    f"Users achieve a median peak rating of {median_max:.0f} "
                    f"(mean: {mean_max:.0f}) across their contest history."
                ),
                "metric": "peak_rating_distribution",
                "category": "rating_progression",
                "confidence": 0.8,
                "data": {
                    "sample_size": len(max_ratings),
                    "median": round(median_max, 1),
                    "mean": round(mean_max, 1),
                    "min": min(max_ratings),
                    "max": max(max_ratings),
                },
            })

        contest_counts = [r.total_contests for r in rows]
        if contest_counts:
            median_contests = statistics.median(contest_counts)
            self._findings.append({
                "title": f"Users participate in median {median_contests:.0f} rated contests",
                "description": (
                    f"The median user has participated in {median_contests:.0f} rated contests. "
                    f"Distribution analysis shows contest participation patterns."
                ),
                "metric": "contest_participation_distribution",
                "category": "rating_progression",
                "confidence": 0.85,
                "data": {
                    "sample_size": len(contest_counts),
                    "median": round(median_contests, 1),
                    "mean": round(statistics.mean(contest_counts), 1),
                },
            })

    async def _analyze_tag_mastery(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(
                Submission.problem_tags,
                func.count(Submission.id).label("count"),
            )
            .where(
                Submission.problem_tags.isnot(None),
                Submission.verdict == "OK",
            )
            .group_by(Submission.problem_tags)
            .order_by(func.count(Submission.id).desc())
            .limit(100)
        )
        rows = result.all()
        if not rows:
            return

        tag_counts: dict[str, int] = {}
        for row in rows:
            tags = row[0]
            cnt: int = row[1] or 0
            if tags:
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + cnt

        sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:15]
        total = sum(tag_counts.values()) if tag_counts else 1
        self._findings.append({
            "title": f"Most solved tag: {sorted_tags[0][0]} ({sorted_tags[0][1]} solves)",
            "description": (
                f"Tag distribution across all solved submissions: "
                + ", ".join(f"{t}({c})" for t, c in sorted_tags[:8])
            ),
            "metric": "tag_solve_distribution",
            "category": "tag_mastery",
            "confidence": 0.9,
            "data": {
                "tags": [{"tag": t, "count": c, "pct": round(c / total * 100, 1)} for t, c in sorted_tags],
            },
        })

    async def _analyze_problems_to_milestone(self, session: AsyncSession) -> None:
        milestones = [1200, 1400, 1600, 1900, 2100, 2400]
        for milestone in milestones:
            counts = await self._compute_solves_before_rating(session, milestone)
            if counts and len(counts) >= 3:
                median_solves = statistics.median(counts)
                self._findings.append({
                    "title": f"Users reaching {milestone} solve median {median_solves:.0f} problems",
                    "description": (
                        f"Analysis of {len(counts)} users who reached rating {milestone}: "
                        f"median {median_solves:.0f} solved problems before milestone."
                    ),
                    "metric": f"problems_before_{milestone}",
                    "category": "milestone_analysis",
                    "confidence": 0.75,
                    "data": {
                        "milestone": milestone,
                        "sample_size": len(counts),
                        "median_solves": round(median_solves, 1),
                        "mean_solves": round(statistics.mean(counts), 1),
                    },
                })

    async def _analyze_contests_to_milestone(self, session: AsyncSession) -> None:
        milestones = [1200, 1400, 1600, 1900, 2100, 2400]
        for milestone in milestones:
            counts = await self._compute_contests_before_rating(session, milestone)
            if counts and len(counts) >= 3:
                median_contests = statistics.median(counts)
                self._findings.append({
                    "title": f"Users reaching {milestone} participate in median {median_contests:.0f} contests",
                    "description": (
                        f"Analysis of {len(counts)} users: median {median_contests:.0f} rated "
                        f"contests before reaching rating {milestone}."
                    ),
                    "metric": f"contests_before_{milestone}",
                    "category": "milestone_analysis",
                    "confidence": 0.8,
                    "data": {
                        "milestone": milestone,
                        "sample_size": len(counts),
                        "median_contests": round(median_contests, 1),
                    },
                })

    async def _analyze_growth_velocity(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("contest_count"),
                func.max(RatingHistory.new_rating) - func.min(RatingHistory.new_rating),
            ).group_by(RatingHistory.user_id)
            .having(func.count(RatingHistory.id) > 1)
        )
        rows = result.all()
        if len(rows) < 5:
            return

        velocities = []
        for user_id, cc, gain in rows:
            if gain and cc:
                velocities.append(gain / cc)

        if velocities:
            median_v = statistics.median(velocities)
            self._findings.append({
                "title": f"Median growth velocity: {median_v:.2f} rating points per contest",
                "description": (
                    f"Among {len(velocities)} users with >1 contest, median growth per contest "
                    f"is {median_v:.2f} rating points. Top quartile grows at >"
                    f"{statistics.quantiles(velocities, n=4)[2]:.2f} per contest."
                ),
                "metric": "growth_velocity",
                "category": "velocity",
                "confidence": 0.7,
                "data": {
                    "sample_size": len(velocities),
                    "median": round(median_v, 2),
                    "q1": round(statistics.quantiles(velocities, n=4)[0], 2) if len(velocities) >= 4 else None,
                    "q3": round(statistics.quantiles(velocities, n=4)[2], 2) if len(velocities) >= 4 else None,
                },
            })

    async def _analyze_growth_predictors(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("contest_count"),
                func.max(RatingHistory.new_rating).label("current_rating"),
            ).group_by(RatingHistory.user_id)
        )
        user_stats = result.all()
        if len(user_stats) < 10:
            return

        result2 = await session.execute(
            select(
                Submission.user_id,
                func.count(Submission.id).label("total_solves"),
            )
            .where(Submission.verdict == "OK")
            .group_by(Submission.user_id)
        )
        sub_stats = {row.user_id: row.total_solves for row in result2.all()}

        combined = []
        for us in user_stats:
            solves = sub_stats.get(us.user_id, 0)
            if us.current_rating and solves > 0:
                combined.append((us.contest_count, solves, us.current_rating))

        if len(combined) < 10:
            return

        contest_counts = [c for c, _, _ in combined]
        solve_counts = [s for _, s, _ in combined]
        ratings = [r for _, _, r in combined]

        if len(contest_counts) > 1:
            r_contests = self._pearson(contest_counts, ratings)
            r_solves = self._pearson(solve_counts, ratings)

            self._findings.append({
                "title": (
                    f"Contest frequency correlates more strongly with rating "
                    f"(r={r_contests:.3f}) than total solves (r={r_solves:.3f})"
                ),
                "description": (
                    f"Pearson correlation between contest count and current rating: "
                    f"{r_contests:.3f}. Between solve count and rating: {r_solves:.3f}. "
                    f"This suggests contest participation frequency is a stronger "
                    f"predictor of rating than raw problem-solving volume."
                ),
                "metric": "growth_predictors",
                "category": "velocity",
                "confidence": 0.65,
                "data": {
                    "sample_size": len(combined),
                    "contest_rating_corr": round(r_contests, 4),
                    "solves_rating_corr": round(r_solves, 4),
                },
            })

    async def _compute_solves_before_rating(
        self, session: AsyncSession, milestone: int
    ) -> list[int]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.min(RatingHistory.contest_time).label("milestone_time"),
            )
            .where(RatingHistory.new_rating >= milestone)
            .group_by(RatingHistory.user_id)
        )
        milestone_users = {r.user_id: r.milestone_time for r in result.all()}
        if not milestone_users:
            return []

        counts = []
        for uid, mt in milestone_users.items():
            sub_result = await session.execute(
                select(func.count(Submission.id))
                .where(
                    Submission.user_id == uid,
                    Submission.verdict == "OK",
                    Submission.submission_time <= mt,
                )
            )
            count = sub_result.scalar_one() or 0
            if count > 0:
                counts.append(count)
        return counts

    async def _compute_contests_before_rating(
        self, session: AsyncSession, milestone: int
    ) -> list[int]:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                func.count(RatingHistory.id).label("contest_num"),
            )
            .where(
                RatingHistory.new_rating >= milestone,
            )
            .group_by(RatingHistory.user_id)
        )
        return [r.contest_num for r in result.all() if r.contest_num]

    async def _analyze_tag_rating_correlation(self, session: AsyncSession) -> None:
        tag_ratings: dict[str, list[int]] = {}
        result = await session.execute(
            select(Submission.problem_tags, Submission.problem_rating)
            .where(
                Submission.verdict == "OK",
                Submission.problem_tags.isnot(None),
                Submission.problem_rating.isnot(None),
            )
            .limit(50000)
        )
        for tags, rating in result.all():
            if tags and rating:
                for tag in tags:
                    tag_ratings.setdefault(tag, []).append(rating)

        tag_stats = []
        for tag, ratings in tag_ratings.items():
            if len(ratings) >= 20:
                tag_stats.append((tag, statistics.mean(ratings), statistics.median(ratings), len(ratings)))

        tag_stats.sort(key=lambda x: -x[1])
        if tag_stats:
            top3 = ", ".join(f"{t}(avg={m:.0f})" for t, m, _, _ in tag_stats[:5])
            bottom3_candidates = [t for t in tag_stats if t[3] >= 50]
            bottom3 = ", ".join(f"{t}(avg={m:.0f})" for t, m, _, _ in bottom3_candidates[-3:]) if len(bottom3_candidates) >= 3 else ""
            self._findings.append({
                "title": f"Tag difficulty hierarchy: highest avg rating {tag_stats[0][0]} ({tag_stats[0][1]:.0f})",
                "description": (
                    f"Tags sorted by average solved problem rating. Top: {top3}. "
                    f"This reveals which problem types are solved at higher rating levels."
                ),
                "metric": "tag_rating_hierarchy",
                "category": "tag_mastery",
                "confidence": 0.78,
                "data": {
                    "sample_size": len(tag_stats),
                    "top_tags": [{"tag": t, "avg_rating": round(m, 1), "median": round(md, 1), "count": c}
                                 for t, m, md, c in tag_stats[:10]],
                },
            })

        if len(tag_stats) >= 5:
            avg_ratings = [m for _, m, _, _ in tag_stats]
            if len(avg_ratings) >= 5:
                q = statistics.quantiles(avg_ratings, n=4)
                self._findings.append({
                    "title": f"Tag difficulty spread: {q[2]-q[0]:.0f} point gap between 25th and 75th percentile tags",
                    "description": (
                        f"Tags span {max(avg_ratings)-min(avg_ratings):.0f} rating points from easiest "
                        f"to hardest. Q1={q[0]:.0f}, Q3={q[2]:.0f}. This quantifies the skill breadth "
                        f"required to advance."
                    ),
                    "metric": "tag_difficulty_spread",
                    "category": "tag_mastery",
                    "confidence": 0.7,
                    "data": {
                        "q1": round(q[0], 1), "q2": round(q[1], 1), "q3": round(q[2], 1),
                        "min": round(min(avg_ratings), 1), "max": round(max(avg_ratings), 1),
                    },
                })

    async def _analyze_contest_pacing(self, session: AsyncSession) -> None:
        result = await session.execute(
            select(
                RatingHistory.user_id,
                RatingHistory.contest_time,
            )
            .order_by(RatingHistory.user_id, RatingHistory.contest_time)
        )
        rows = result.all()
        if len(rows) < 20:
            return

        intervals: list[float] = []
        user_intervals: dict[int, list[float]] = {}
        prev_user = None
        prev_time = None
        for uid, ct in rows:
            if ct is None:
                continue
            if uid == prev_user and prev_time is not None:
                days = (ct - prev_time).total_seconds() / 86400
                if 1 <= days <= 365:
                    intervals.append(days)
                    user_intervals.setdefault(uid, []).append(days)
            prev_user = uid
            prev_time = ct

        if len(intervals) < 10:
            return

        median_interval = statistics.median(intervals)
        mean_interval = statistics.mean(intervals)

        self._findings.append({
            "title": f"Median time between contests: {median_interval:.1f} days",
            "description": (
                f"Across all users, median gap between rated contests is {median_interval:.1f} days "
                f"(mean: {mean_interval:.1f}). Analyzed {len(intervals)} intervals from "
                f"{len(user_intervals)} users."
            ),
            "metric": "contest_pacing",
            "category": "rating_progression",
            "confidence": 0.85,
            "data": {
                "sample_size": len(intervals),
                "median_days": round(median_interval, 1),
                "mean_days": round(mean_interval, 1),
                "user_count": len(user_intervals),
            },
        })

        user_variances: list[tuple[int, float]] = []
        for uid, vals in user_intervals.items():
            if len(vals) >= 3:
                user_variances.append((uid, statistics.stdev(vals) / statistics.mean(vals) if statistics.mean(vals) > 0 else 0))

        if len(user_variances) >= 5:
            cvs = [cv for _, cv in user_variances]
            median_cv = statistics.median(cvs)
            if len(cvs) >= 4:
                q = statistics.quantiles(cvs, n=4)
                self._findings.append({
                    "title": f"Consistency score (CV of contest intervals): median {median_cv:.2f}",
                    "description": (
                        f"Lower CV means more consistent participation. Q1={q[0]:.2f}, Q3={q[2]:.2f}. "
                        f"Users in Q1 (most consistent) participate at very regular intervals."
                    ),
                    "metric": "contest_pacing_consistency",
                    "category": "rating_progression",
                    "confidence": 0.75,
                    "data": {
                        "median_cv": round(median_cv, 3),
                        "q1": round(q[0], 3), "q3": round(q[2], 3),
                        "sample_size": len(user_variances),
                    },
                })

    async def _analyze_skill_graph(self, session: AsyncSession) -> None:
        transitions = (
            await session.execute(
                select(TagTransition).order_by(TagTransition.transition_count.desc())
            )
        ).scalars().all()

        if len(transitions) < 5:
            return

        top_edges = [t for t in transitions if t.user_count >= 3][:10]
        if not top_edges:
            return

        top_str = ", ".join(
            f"{t.source_tag}→{t.target_tag}({t.transition_count})"
            for t in top_edges[:5]
        )
        self._findings.append({
            "title": f"Top skill transition: {top_edges[0].source_tag} → {top_edges[0].target_tag} "
                     f"({top_edges[0].transition_count} transitions, {top_edges[0].user_count} users)",
            "description": (
                f"Most common tag-to-tag transitions from {len(transitions)} total edges. "
                f"Top: {top_str}. "
                f"This reveals common skill progression paths."
            ),
            "metric": "skill_graph_top_transitions",
            "category": "skill_graph",
            "confidence": 0.8,
            "data": {
                "total_edges": len(transitions),
                "top_edges": [
                    {"source": t.source_tag, "target": t.target_tag,
                     "count": t.transition_count, "users": t.user_count,
                     "avg_rating_gain": t.avg_rating_gain}
                    for t in top_edges
                ],
            },
        })

        high_gain = [t for t in transitions
                     if t.user_count >= 3 and t.avg_rating_gain > 50]
        high_gain.sort(key=lambda t: -t.avg_rating_gain)
        if high_gain:
            top5 = high_gain[:5]
            hg_str = ", ".join(
                f"{t.source_tag}→{t.target_tag}(+{t.avg_rating_gain:.0f})"
                for t in top5
            )
            self._findings.append({
                "title": f"Highest rating-gain transition: {top5[0].source_tag} → {top5[0].target_tag} "
                         f"(avg +{top5[0].avg_rating_gain:.0f} rating)",
                "description": (
                    f"Tag transitions associated with highest immediate rating gains. "
                    f"Top: {hg_str}. These transitions may indicate breakthrough skill acquisitions."
                ),
                "metric": "skill_graph_highest_gain",
                "category": "skill_graph",
                "confidence": 0.65,
                "data": {
                    "sample_size": len(high_gain),
                    "high_gain_edges": [
                        {"source": t.source_tag, "target": t.target_tag,
                         "avg_gain": round(t.avg_rating_gain, 1), "users": t.user_count}
                        for t in top5
                    ],
                },
            })

        upward = [t for t in transitions
                  if t.user_count >= 3 and t.avg_target_rating and t.avg_source_rating
                  and t.avg_target_rating > t.avg_source_rating + 50]
        if upward:
            self._findings.append({
                "title": f"{len(upward)} upward transitions found where target problems average "
                         f"50+ rating points harder than source",
                "description": (
                    f"Transitions to significantly harder problems ({len(upward)} edges) indicate "
                    f"users leveling up. Most common upward transitions often involve "
                    f"{upward[0].source_tag}→{upward[0].target_tag}."
                ),
                "metric": "skill_graph_upward_transitions",
                "category": "skill_graph",
                "confidence": 0.7,
                "data": {
                    "upward_count": len(upward),
                    "upward_edges": [
                        {"source": t.source_tag, "target": t.target_tag,
                         "src_rating": round(t.avg_source_rating, 0) if t.avg_source_rating else 0,
                         "tgt_rating": round(t.avg_target_rating, 0) if t.avg_target_rating else 0}
                        for t in upward[:8]
                    ],
                },
            })

        loops = [t for t in transitions
                 if t.source_tag == t.target_tag and t.user_count >= 3]
        if loops:
            self._findings.append({
                "title": f"Self-loop transitions found: users practice same-tag problems consecutively",
                "description": (
                    f"{len(loops)} tag self-loops detected — users often solve multiple problems "
                    f"with the same tag in sequence, indicating focused practice sessions."
                ),
                "metric": "skill_graph_self_loops",
                "category": "skill_graph",
                "confidence": 0.75,
                "data": {
                    "self_loop_count": len(loops),
                    "top_self_loops": [
                        {"tag": t.source_tag, "count": t.transition_count, "users": t.user_count}
                        for t in sorted(loops, key=lambda x: -x.transition_count)[:5]
                    ],
                },
            })

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
