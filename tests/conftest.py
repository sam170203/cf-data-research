"""Test fixtures."""
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_cf_client():
    """Returns a mock CodeforcesClient."""
    mock = AsyncMock()
    mock.fetch_user_profile = AsyncMock(return_value={
        "handle": "test_user",
        "rating": 1500,
        "maxRating": 1600,
        "rank": "specialist",
        "maxRank": "expert",
        "country": "Testland",
        "organization": "Test Org",
    })
    mock.fetch_rating_history = AsyncMock(return_value=[
        {
            "contestId": 1,
            "contestName": "Test Contest",
            "oldRating": 1400,
            "newRating": 1500,
            "rank": 100,
            "ratingUpdateTimeSeconds": 1000000,
        }
    ])
    mock.fetch_all_submissions = AsyncMock(return_value=[
        {
            "id": 12345,
            "contestId": 1,
            "problem": {"index": "A", "name": "Test Problem", "rating": 800, "tags": ["math"]},
            "verdict": "OK",
            "programmingLanguage": "Python",
            "creationTimeSeconds": 1000000,
        }
    ])
    return mock
