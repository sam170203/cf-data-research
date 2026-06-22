from __future__ import annotations

import logging
import os
import pickle
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import load_only

from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User

logger = logging.getLogger("research.features")

ALL_TAGS = [
    "implementation", "math", "greedy", "dp", "data structures", "binary search",
    "brute force", "graphs", "sortings", "strings", "number theory", "geometry",
    "combinatorics", "dfs and similar", "trees", "two pointers", "dsu",
    "bitmasks", "probabilities", "shortest paths", "hashing", "divide and conquer",
    "constructive algorithms", "fft", "flows", "games", "matrices", "ternary search",
    "expression parsing", "meet-in-the-middle", "schedules",
    "graph matchings", "2-sat",
]

TAG_COLUMNS = [f"tag_{t.replace(' ', '_').replace('-', '_')}" for t in ALL_TAGS]


class _SubmissionShim:
    __slots__ = ('id', 'user_id', 'problem_rating', 'problem_tags', 'verdict', 'submission_time')
    def __init__(self, id, user_id, problem_rating, problem_tags, verdict, submission_time):
        self.id = id
        self.user_id = user_id
        self.problem_rating = problem_rating
        self.problem_tags = problem_tags
        self.verdict = verdict
        self.submission_time = submission_time


class FeatureComputer:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    def _cache_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), ".feature_matrix.pkl")

    def _cache_is_valid(self) -> bool:
        path = self._cache_path()
        if not os.path.exists(path):
            return False
        age = (datetime.now(UTC).timestamp() - os.path.getmtime(path)) / 3600
        return age < 24

    def _load_cache(self) -> pd.DataFrame | None:
        try:
            with open(self._cache_path(), "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def _save_cache(self, df: pd.DataFrame) -> None:
        try:
            with open(self._cache_path(), "wb") as f:
                pickle.dump(df, f)
        except Exception as e:
            logger.warning("Failed to cache feature matrix: %s", e)

    async def build_feature_matrix(self, include_labels: bool = True) -> pd.DataFrame:
        if self._cache_is_valid():
            cached = self._load_cache()
            if cached is not None:
                logger.info("Using cached feature matrix (%d rows)", len(cached))
                return cached

        async with self._sf() as session:
            users = (
                await session.execute(
                    select(User.id, User.cf_handle, User.current_rating, User.max_rating)
                )
            ).all()
            logger.info("Building features for %d users", len(users))

            all_rh = (
                await session.execute(
                    select(RatingHistory)
                )
            ).scalars().all()
            logger.info("Loaded %d rating_history rows", len(all_rh))

            conn = await session.connection()
            await conn.exec_driver_sql("SET statement_timeout = '300000'")

            all_subs_raw: list[Any] = []
            offset = 0
            chunk_size = 50000
            while True:
                chunk = (
                    await session.execute(
                        text(
                            "SELECT id, user_id, problem_rating, problem_tags, "
                            "verdict, submission_time FROM submissions "
                            "ORDER BY id LIMIT :limit OFFSET :offset"
                        ),
                        {"limit": chunk_size, "offset": offset},
                    )
                ).all()
                if not chunk:
                    break
                all_subs_raw.extend(chunk)
                offset += len(chunk)
                if len(all_subs_raw) % 100000 == 0:
                    logger.info("  Loaded %d submissions...", len(all_subs_raw))
            logger.info("Loaded %d submissions", len(all_subs_raw))

        rh_by_user: dict[int, list] = {}
        for rh in all_rh:
            rh_by_user.setdefault(rh.user_id, []).append(rh)
        for uid in rh_by_user:
            rh_by_user[uid].sort(key=lambda r: r.contest_time or datetime.min)

        subs_by_user: dict[int, list] = {}
        for row in all_subs_raw:
            s = _SubmissionShim(*row)
            subs_by_user.setdefault(s.user_id, []).append(s)
        for uid in subs_by_user:
            subs_by_user[uid].sort(key=lambda s: s.submission_time or datetime.min)

        rows: list[dict[str, Any]] = []
        for user in users:
            try:
                row = self._compute_features_for_user(
                    user, rh_by_user.get(user.id, []), subs_by_user.get(user.id, []),
                )
                rows.append(row)
            except Exception as e:
                logger.warning("Feature error for user %d: %s", user.id, e)

        df = pd.DataFrame(rows)
        logger.info(
            "Feature matrix: %d rows, %d cols",
            len(df), len(df.columns),
        )

        if include_labels:
            df = self._build_labels(df, rh_by_user)
            n_labels = sum(1 for c in df.columns if c.startswith("target_"))
            logger.info("Added %d label columns", n_labels)

        self._save_cache(df)
        return df

    def _compute_features_for_user(
        self, user: tuple, rh_rows: list, sub_rows: list
    ) -> dict[str, Any]:
        user_id, handle, current_rating, max_rating = user
        features: dict[str, Any] = {
            "user_id": user_id,
            "handle": handle,
            "current_rating": current_rating or 0,
            "max_rating": max_rating or 0,
        }

        self._add_activity_features(features, sub_rows)
        self._add_performance_features(features, rh_rows)
        self._add_tag_features(features, sub_rows)
        self._add_temporal_features(features, sub_rows, rh_rows)

        return features

    def _add_activity_features(
        self, features: dict[str, Any], subs: list
    ) -> None:
        features["total_submissions"] = len(subs)
        solved = [s for s in subs if s.verdict == "OK"]
        features["total_solved"] = len(solved)

        if subs and subs[0].submission_time and subs[-1].submission_time:
            span = (subs[-1].submission_time - subs[0].submission_time).total_seconds()
            span_days = span / 86400 if span > 0 else 1
            features["submissions_per_day"] = round(len(subs) / span_days, 4)
            features["active_days"] = len(set(
                s.submission_time.date() for s in subs if s.submission_time
            ))
        else:
            features["submissions_per_day"] = 0.0
            features["active_days"] = 0

        if subs:
            dates = sorted(set(
                s.submission_time.date() for s in subs if s.submission_time
            ))
            if len(dates) >= 2:
                gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
                features["max_inactivity_streak"] = max(gaps)
                features["median_inactivity_gap"] = round(statistics.median(gaps), 2)
            else:
                features["max_inactivity_streak"] = 0
                features["median_inactivity_gap"] = 0.0
        else:
            features["max_inactivity_streak"] = 0
            features["median_inactivity_gap"] = 0.0

    def _add_performance_features(
        self, features: dict[str, Any], rh_rows: list
    ) -> None:
        features["total_contests"] = len(rh_rows)

        if rh_rows:
            deltas = [r.rating_change for r in rh_rows]
            features["avg_contest_delta"] = round(
                statistics.mean(deltas), 2
            ) if deltas else 0
            features["rating_volatility"] = round(
                statistics.stdev(deltas), 2
            ) if len(deltas) >= 2 else 0

            ratings = [r.new_rating for r in rh_rows]
            features["first_rating"] = rh_rows[0].old_rating
            features["current_rating"] = rh_rows[-1].new_rating
            features["peak_rating"] = max(ratings)
            features["rating_gain_total"] = ratings[-1] - rh_rows[0].old_rating

            win_streak = 0
            loss_streak = 0
            max_win = 0
            max_loss = 0
            for r in rh_rows:
                if r.rating_change > 0:
                    win_streak += 1
                    loss_streak = 0
                    max_win = max(max_win, win_streak)
                elif r.rating_change < 0:
                    loss_streak += 1
                    win_streak = 0
                    max_loss = max(max_loss, loss_streak)
                else:
                    win_streak = 0
                    loss_streak = 0
            features["max_win_streak"] = max_win
            features["max_loss_streak"] = max_loss
        else:
            features["avg_contest_delta"] = 0.0
            features["rating_volatility"] = 0.0
            features["first_rating"] = 0
            features["rating_gain_total"] = 0
            features["max_win_streak"] = 0
            features["max_loss_streak"] = 0

    def _add_tag_features(
        self, features: dict[str, Any], subs: list
    ) -> None:
        solved = [s for s in subs if s.verdict == "OK" and s.problem_tags]
        if not solved:
            features["tag_diversity"] = 0
            features["hardest_solved_tag_rating"] = 0
            for tc in TAG_COLUMNS:
                features[tc] = 0.0
            return

        tag_counts: dict[str, int] = {}
        for s in solved:
            for tag in (s.problem_tags or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        features["tag_diversity"] = len(tag_counts)
        total = sum(tag_counts.values()) or 1

        solved_with_rating = [s for s in subs if s.verdict == "OK" and s.problem_rating]
        if solved_with_rating:
            tag_ratings: dict[str, list[int]] = {}
            for s in solved_with_rating:
                for tag in (s.problem_tags or []):
                    tag_ratings.setdefault(tag, []).append(s.problem_rating)
            hardest = max(
                (statistics.mean(rs) for rs in tag_ratings.values() if len(rs) >= 3),
                default=0,
            )
            features["hardest_solved_tag_rating"] = round(hardest, 1)
        else:
            features["hardest_solved_tag_rating"] = 0

        for tag, col in zip(ALL_TAGS, TAG_COLUMNS):
            features[col] = round(tag_counts.get(tag, 0) / total, 4)

        solved_ratings = [s.problem_rating for s in solved_with_rating if s.problem_rating]
        features["avg_solved_rating"] = round(
            statistics.mean(solved_ratings), 1
        ) if solved_ratings else 0

    def _add_temporal_features(
        self, features: dict[str, Any], subs: list, rh_rows: list
    ) -> None:
        now = datetime.now(UTC)
        windows = [30, 60, 90]
        for w in windows:
            cutoff = now - timedelta(days=w)
            recent_subs = [s for s in subs if s.submission_time and s.submission_time >= cutoff]
            features[f"activity_last_{w}d"] = len(recent_subs)
            solved_recent = [s for s in recent_subs if s.verdict == "OK"]
            features[f"solved_last_{w}d"] = len(solved_recent)

        if rh_rows:
            gains = [r.rating_change for r in rh_rows]
            n = len(gains)
            if n >= 2:
                features["growth_velocity"] = round(
                    statistics.mean(gains[-min(5, n):]), 2
                )
            else:
                features["growth_velocity"] = gains[0] if gains else 0

            if n >= 3:
                recent = gains[-min(5, n):]
                if len(recent) >= 2:
                    accel = recent[-1] - recent[0]
                    features["growth_acceleration"] = round(accel / max(len(recent) - 1, 1), 2)
                else:
                    features["growth_acceleration"] = 0.0
            else:
                features["growth_acceleration"] = 0.0

            features["rating_volatility_recent"] = round(
                statistics.stdev(gains[-min(10, n):]), 2
            ) if len(gains) >= 2 else 0

            features["contests_last_90d"] = len([
                r for r in rh_rows
                if r.contest_time and r.contest_time >= now - timedelta(days=90)
            ])
        else:
            features["growth_velocity"] = 0.0
            features["growth_acceleration"] = 0.0
            features["rating_volatility_recent"] = 0.0
            features["contests_last_90d"] = 0

    def _build_labels(self, df: pd.DataFrame, rh_by_user: dict[int, list]) -> pd.DataFrame:
        result = df.copy()
        for col in [
            "target_expert_6mo", "target_cm_12mo", "target_master_12mo",
            "target_gain_100_90d", "target_expert_12mo", "target_plateau_risk",
            "target_rating_3mo", "target_rating_6mo", "target_rating_12mo",
            "target_rating_90d", "target_rating_180d",
        ]:
            result[col] = -1

        for idx, row in result.iterrows():
            uid = row["user_id"]
            rh = rh_by_user.get(uid, [])
            if len(rh) < 2:
                continue

            start_time = rh[0].contest_time
            if not start_time:
                continue

            window_3mo = start_time + timedelta(days=90)
            window_6mo = start_time + timedelta(days=180)
            window_12mo = start_time + timedelta(days=365)

            rh_3mo = [r for r in rh if r.contest_time <= window_3mo]
            rh_6mo = [r for r in rh if r.contest_time <= window_6mo]
            rh_12mo = [r for r in rh if r.contest_time <= window_12mo]

            if rh_6mo:
                result.at[idx, "target_expert_6mo"] = (
                    1 if max(r.new_rating for r in rh_6mo) >= 1600 else 0
                )
            if rh_12mo:
                result.at[idx, "target_master_12mo"] = (
                    1 if max(r.new_rating for r in rh_12mo) >= 2100 else 0
                )
                result.at[idx, "target_cm_12mo"] = (
                    1 if max(r.new_rating for r in rh_12mo) >= 1900 else 0
                )
                result.at[idx, "target_expert_12mo"] = (
                    1 if max(r.new_rating for r in rh_12mo) >= 1600 else 0
                )

            result.at[idx, "target_rating_3mo"] = rh_3mo[-1].new_rating if rh_3mo else -1
            result.at[idx, "target_rating_6mo"] = rh_6mo[-1].new_rating if rh_6mo else -1
            result.at[idx, "target_rating_12mo"] = rh_12mo[-1].new_rating if rh_12mo else -1
            result.at[idx, "target_rating_90d"] = rh_3mo[-1].new_rating if rh_3mo else -1
            result.at[idx, "target_rating_180d"] = rh_6mo[-1].new_rating if rh_6mo else -1

            gain_100_90d = 0
            for i in range(len(rh)):
                window_end = rh[i].contest_time + timedelta(days=90)
                future = [r for r in rh if rh[i].contest_time <= r.contest_time <= window_end]
                if len(future) >= 2:
                    gain = future[-1].new_rating - future[0].old_rating
                    if gain >= 100:
                        gain_100_90d = 1
                        break
            result.at[idx, "target_gain_100_90d"] = gain_100_90d

            if len(rh) >= 3:
                last_three_gain = sum(r.rating_change for r in rh[-3:])
                result.at[idx, "target_plateau_risk"] = 1 if last_three_gain < 20 else 0
            elif len(rh) >= 1:
                result.at[idx, "target_plateau_risk"] = 0

        return result
