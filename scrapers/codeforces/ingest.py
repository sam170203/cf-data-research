from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import Contest
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User
from app.services.codeforces import CodeforcesAPIError, CodeforcesClient

logger = logging.getLogger(__name__)


async def ingest_user_profile(
    client: CodeforcesClient,
    session: AsyncSession,
    handle: str,
) -> User | None:
    """Fetch and store a Codeforces user profile. Returns the User or None."""
    try:
        data = await client.fetch_user_profile(handle)
    except CodeforcesAPIError as e:
        logger.warning("Failed to fetch profile for %s: %s", handle, e)
        return None

    if not data:
        logger.warning("No profile data for %s", handle)
        return None

    result = await session.execute(select(User).where(User.cf_handle == handle))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(cf_handle=handle)

    _update_user_from_api(user, data)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _update_user_from_api(user: User, data: dict[str, Any]) -> None:
    user.current_rating = data.get("rating")
    user.max_rating = data.get("maxRating")
    user.rank = data.get("rank")
    user.max_rank = data.get("maxRank")
    user.country = data.get("country")
    user.city = data.get("city")
    user.organization = data.get("organization")
    user.contribution = data.get("contribution")
    user.friend_of_count = data.get("friendOfCount")
    user.last_online_time = _parse_unix(data.get("lastOnlineTimeSeconds"))
    user.registration_time = _parse_unix(data.get("registrationTimeSeconds"))
    user.avatar = data.get("avatar")
    user.title_photo = data.get("titlePhoto")


async def ingest_rating_history(
    client: CodeforcesClient,
    session: AsyncSession,
    user: User,
) -> int:
    """Fetch and store rating history for a user. Returns count of new rows."""
    try:
        data = await client.fetch_rating_history(user.cf_handle)
    except CodeforcesAPIError as e:
        logger.warning("Failed to fetch rating history for %s: %s", user.cf_handle, e)
        return 0

    if not data:
        return 0

    contest_ids = [e["contestId"] for e in data if e.get("contestId") is not None]
    if contest_ids:
        result = await session.execute(
            select(RatingHistory.contest_id).where(
                RatingHistory.user_id == user.id,
                RatingHistory.contest_id.in_(contest_ids),
            )
        )
        existing = {row[0] for row in result}
    else:
        existing = set()

    values = []
    for entry in data:
        contest_id = entry.get("contestId")
        if contest_id is None or contest_id in existing:
            continue
        old_rating = entry.get("oldRating", 0) or 0
        new_rating = entry.get("newRating", 0) or 0
        values.append({
            "user_id": user.id,
            "contest_id": contest_id,
            "contest_name": entry.get("contestName", ""),
            "old_rating": old_rating,
            "new_rating": new_rating,
            "rating_change": new_rating - old_rating,
            "rank": entry.get("rank"),
            "contest_time": _parse_unix(entry.get("ratingUpdateTimeSeconds")),
        })

    if values:
        await session.execute(insert(RatingHistory), values)
        await session.commit()
    return len(values)


async def ingest_submissions(
    client: CodeforcesClient,
    session: AsyncSession,
    user: User,
) -> int:
    """Fetch and store submission history for a user. Returns count of new rows."""
    try:
        data = await client.fetch_all_submissions(user.cf_handle)
    except CodeforcesAPIError as e:
        logger.warning("Failed to fetch submissions for %s: %s", user.cf_handle, e)
        return 0

    if not data:
        return 0

    values = []
    for entry in data:
        sub_id = entry.get("id")
        if sub_id is None:
            continue
        problem = entry.get("problem", {})
        tags = problem.get("tags")
        values.append({
            "id": sub_id,
            "user_id": user.id,
            "contest_id": entry.get("contestId"),
            "problem_index": problem.get("index"),
            "problem_name": problem.get("name"),
            "problem_rating": problem.get("rating"),
            "problem_tags": tags if tags else None,
            "verdict": entry.get("verdict"),
            "programming_language": entry.get("programmingLanguage"),
            "submission_time": _parse_unix(entry.get("creationTimeSeconds")),
        })

    if not values:
        return 0

    stmt = insert(Submission).on_conflict_do_nothing(index_elements=["id"])
    await session.execute(stmt, values)
    await session.commit()
    return len(values)


async def ingest_contests(
    client: CodeforcesClient,
    session: AsyncSession,
) -> int:
    """Fetch and store all Codeforces contests. Returns count of new rows."""
    try:
        data = await client.get_cached_contest_list()
    except CodeforcesAPIError as e:
        logger.warning("Failed to fetch contest list: %s", e)
        return 0

    if not data:
        return 0

    values = []
    for entry in data:
        cid = entry.get("id")
        if cid is None:
            continue
        values.append({
            "contest_id": cid,
            "name": entry.get("name", ""),
            "type": entry.get("type", ""),
            "phase": entry.get("phase", ""),
            "start_time": _parse_unix(entry.get("startTimeSeconds")),
            "duration": entry.get("durationSeconds"),
            "prepared_by": entry.get("preparedBy"),
            "difficulty": entry.get("difficulty"),
            "kind": entry.get("kind"),
            "country": entry.get("country"),
            "season": entry.get("season"),
            "description": entry.get("description"),
        })

    if not values:
        return 0

    stmt = insert(Contest).on_conflict_do_nothing(index_elements=["contest_id"])
    await session.execute(stmt, values)
    await session.commit()
    return len(values)


async def ingest_problems(
    client: CodeforcesClient,
    session: AsyncSession,
) -> int:
    """Fetch and store all Codeforces problems. Returns count of new rows."""
    try:
        data = await client.get_cached_problems()
    except CodeforcesAPIError as e:
        logger.warning("Failed to fetch problems: %s", e)
        return 0

    if not data:
        return 0

    values = []
    for entry in data:
        cid = entry.get("contestId")
        idx = entry.get("index")
        if cid is None or not idx:
            continue
        tags = entry.get("tags", [])
        values.append({
            "contest_id": cid,
            "index": idx,
            "name": entry.get("name", ""),
            "rating": entry.get("rating"),
            "tags": tags if tags else None,
            "solved_count": entry.get("solvedCount"),
        })

    if not values:
        return 0

    stmt = insert(Problem).on_conflict_do_nothing(
        index_elements=["contest_id", "index"]
    )
    await session.execute(stmt, values)
    await session.commit()
    return len(values)


async def ingest_all_user_data(
    client: CodeforcesClient,
    session: AsyncSession,
    handle: str,
) -> dict[str, Any]:
    """Fetch and store all data for a single user.
    Returns a summary dict."""
    user = await ingest_user_profile(client, session, handle)
    if not user:
        return {"handle": handle, "status": "failed", "reason": "no profile"}

    rating_count = await ingest_rating_history(client, session, user)
    submission_count = await ingest_submissions(client, session, user)

    from app.models.contest import Contest
    from app.models.problem import Problem
    from sqlalchemy import func

    existing_contests = (await session.execute(
        select(func.count()).select_from(Contest)
    )).scalar_one() or 0
    existing_problems = (await session.execute(
        select(func.count()).select_from(Problem)
    )).scalar_one() or 0

    contest_count = 0
    problem_count = 0
    if existing_contests == 0:
        contest_count = await ingest_contests(client, session)
    if existing_problems == 0:
        problem_count = await ingest_problems(client, session)

    return {
        "handle": handle,
        "status": "success",
        "user_id": user.id,
        "current_rating": user.current_rating,
        "rating_histories_count": rating_count,
        "submissions_count": submission_count,
        "contests_count": contest_count or existing_contests,
        "problems_count": problem_count or existing_problems,
    }


def _parse_unix(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)
