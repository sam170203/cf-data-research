"""Tests for Codeforces client and ingestion."""
import pytest

from app.services.codeforces import CodeforcesClient, RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = RateLimiter(requests_per_second=100.0)
    import time
    t0 = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_client_init():
    client = CodeforcesClient()
    assert client.BASE_URL == "https://codeforces.com/api"
    assert client.MAX_RETRIES == 3
    await client.close()


@pytest.mark.asyncio
async def test_mock_ingestion(mock_cf_client):
    """Verify mock client returns expected data."""
    profile = await mock_cf_client.fetch_user_profile("test_user")
    assert profile["handle"] == "test_user"
    assert profile["rating"] == 1500

    history = await mock_cf_client.fetch_rating_history("test_user")
    assert len(history) == 1
    assert history[0]["contestId"] == 1

    subs = await mock_cf_client.fetch_all_submissions("test_user")
    assert len(subs) == 1
    assert subs[0]["verdict"] == "OK"
