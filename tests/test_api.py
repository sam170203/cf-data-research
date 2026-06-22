"""Tests for API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CF Growth Lab"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires PostgreSQL database")
async def test_metrics_endpoint(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "rating_histories" in data
    assert "submissions" in data


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires PostgreSQL database")
async def test_research_status(client):
    response = await client.get("/research-status")
    assert response.status_code == 200
    data = response.json()
    assert "dataset_status" in data


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires PostgreSQL database")
async def test_list_jobs(client):
    response = await client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires PostgreSQL database")
async def test_top_users(client):
    response = await client.get("/stats/top-users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires PostgreSQL database")
async def test_rating_distribution(client):
    response = await client.get("/stats/rating-distribution")
    assert response.status_code == 200
    data = response.json()
    assert "distribution" in data
