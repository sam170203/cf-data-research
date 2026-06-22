from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User


async def get_users_reaching_rating(
    session: AsyncSession, target_rating: int
) -> pd.DataFrame:
    """Returns users who have ever reached a given rating, with their first
    contest date reaching it."""
    subq = (
        select(
            RatingHistory.user_id,
            func.min(RatingHistory.contest_time).label("first_reached_at"),
            func.min(RatingHistory.contest_id).label("first_reached_contest"),
        )
        .where(RatingHistory.new_rating >= target_rating)
        .group_by(RatingHistory.user_id)
    ).subquery()

    query = (
        select(
            User.cf_handle,
            User.current_rating,
            User.max_rating,
            User.rank,
            subq.c.first_reached_at,
            subq.c.first_reached_contest,
        )
        .join(subq, User.id == subq.c.user_id)
        .order_by(subq.c.first_reached_at)
    )

    result = await session.execute(query)
    rows = result.all()
    return pd.DataFrame(
        rows,
        columns=[
            "cf_handle",
            "current_rating",
            "max_rating",
            "rank",
            "first_reached_at",
            "first_reached_contest",
        ],
    )


async def get_average_problems_before_rating(
    session: AsyncSession, target_rating: int
) -> pd.DataFrame:
    """Returns average number of problems solved before reaching target rating."""
    rating_subq = (
        select(
            RatingHistory.user_id,
            func.min(RatingHistory.contest_time).label("reached_at"),
        )
        .where(RatingHistory.new_rating >= target_rating)
        .group_by(RatingHistory.user_id)
    ).subquery()

    query = (
        select(
            User.cf_handle,
            rating_subq.c.reached_at,
            func.count(Submission.id).label("problems_solved"),
        )
        .join(rating_subq, User.id == rating_subq.c.user_id)
        .join(
            Submission,
            and_(
                Submission.user_id == User.id,
                Submission.submission_time <= rating_subq.c.reached_at,
                Submission.verdict == "OK",
            ),
        )
        .group_by(User.cf_handle, rating_subq.c.reached_at)
    )

    result = await session.execute(query)
    rows = result.all()
    return pd.DataFrame(
        rows,
        columns=["cf_handle", "reached_at", "problems_solved"],
    )


async def get_tag_distribution_by_rating_bucket(
    session: AsyncSession,
) -> pd.DataFrame:
    """Returns tag frequency distribution across rating buckets."""
    rating_buckets = [
        (0, 1199, "0-1199"),
        (1200, 1399, "1200-1399"),
        (1400, 1599, "1400-1599"),
        (1600, 1899, "1600-1899"),
        (1900, 2199, "1900-2199"),
        (2200, 3000, "2200-3000"),
    ]

    records: list[dict[str, Any]] = []
    for lo, hi, label in rating_buckets:
        query = select(Submission.problem_tags).where(
            Submission.problem_rating >= lo,
            Submission.problem_rating <= hi,
            Submission.problem_tags.isnot(None),
            Submission.verdict == "OK",
        )
        result = await session.execute(query)
        tags_list = result.scalars().all()
        tag_counts: dict[str, int] = {}
        for tags in tags_list:
            if tags:
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:20]:
            records.append({"rating_bucket": label, "tag": tag, "count": count})

    return pd.DataFrame(records)


async def get_fastest_growth_users(
    session: AsyncSession, min_contests: int = 5
) -> pd.DataFrame:
    """Identifies users with the fastest rating growth per contest."""
    subq = (
        select(
            RatingHistory.user_id,
            func.count(RatingHistory.id).label("contest_count"),
            func.min(RatingHistory.new_rating).label("min_rating"),
            func.max(RatingHistory.new_rating).label("max_rating"),
            func.min(RatingHistory.contest_time).label("first_contest"),
            func.max(RatingHistory.contest_time).label("last_contest"),
        )
        .group_by(RatingHistory.user_id)
        .having(func.count(RatingHistory.id) >= min_contests)
    ).subquery()

    query = (
        select(
            User.cf_handle,
            subq.c.contest_count,
            subq.c.min_rating,
            subq.c.max_rating,
            (subq.c.max_rating - subq.c.min_rating).label("total_growth"),
            (
                (subq.c.max_rating - subq.c.min_rating) / subq.c.contest_count
            ).label("growth_per_contest"),
            subq.c.first_contest,
            subq.c.last_contest,
        )
        .join(subq, User.id == subq.c.user_id)
        .order_by((subq.c.max_rating - subq.c.min_rating) / subq.c.contest_count)
    )

    result = await session.execute(query)
    rows = result.all()
    return pd.DataFrame(
        rows,
        columns=[
            "cf_handle",
            "contest_count",
            "min_rating",
            "max_rating",
            "total_growth",
            "growth_per_contest",
            "first_contest",
            "last_contest",
        ],
    )
