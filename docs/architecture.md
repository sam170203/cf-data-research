# CF Growth Lab — Architecture

## Overview

CF Growth Lab is a research platform for analyzing the growth trajectories of elite Codeforces users. It collects, stores, and analyzes competitive programming data to answer questions about rating progression, skill acquisition patterns, and problem-solving trajectories.

## High-Level Design

```
┌────────────────────────────────────────────────────────────┐
│                     Data Sources                            │
│  Codeforces API (user.info, user.rating, user.status)      │
└─────────────────────┬──────────────────────────────────────┘
                      │ httpx (async, rate-limited)
┌─────────────────────▼──────────────────────────────────────┐
│                   Scrapers                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  collect_top_users.py  │  ingest_user.py             │   │
│  └──────────────────────────────────────────────────────┘   │
│  - Rate limiting (1 req/sec)                                │
│  - Retry with exponential backoff                           │
│  - Job progress tracking                                   │
└─────────────────────┬──────────────────────────────────────┘
                      │ SQLAlchemy 2.0 (async)
┌─────────────────────▼──────────────────────────────────────┐
│                   PostgreSQL                                │
│  users | rating_history | contests | problems | submissions │
│  ingestion_jobs | ingestion_job_items                      │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                   Analysis Layer                            │
│  - get_users_reaching_rating()                              │
│  - get_average_problems_before_rating()                     │
│  - get_tag_distribution_by_rating_bucket()                  │
│  - get_fastest_growth_users()                               │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│              FastAPI Research Dashboard                     │
│  /stats/top-users                                           │
│  /stats/rating-distribution                                 │
│  /stats/tag-distribution                                    │
│  /users/{handle}/summary                                    │
│  /jobs                                                      │
│  /jobs/{job_id}                                             │
│  /metrics                                                   │
│  /research-status                                           │
└────────────────────────────────────────────────────────────┘
```

## Directory Structure

| Path | Purpose |
|------|---------|
| `app/api/` | FastAPI routes and app setup |
| `app/core/` | Configuration and shared utilities |
| `app/db/` | Database session and base model |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic v2 request/response schemas |
| `app/services/` | Business logic (CF client, ingestion, analysis) |
| `scrapers/codeforces/` | CF API data ingestion logic |
| `scrapers/jobs/` | CLI collection jobs |
| `analysis/` | Analysis function re-exports |
| `alembic/` | Database migrations |
| `tests/` | pytest test suite |
| `docs/` | Project documentation |
| `notebooks/` | Jupyter notebooks for ad-hoc research |

## Key Design Decisions

### Async Throughout
The entire stack uses async/await — httpx for HTTP, SQLAlchemy async sessions for DB, FastAPI for API. This allows efficient concurrent data collection.

### Rate-Limited API Client
The Codeforces API enforces rate limits (~1 request/second). The `RateLimiter` class ensures we never exceed this, and the retry logic handles transient 503 errors with exponential backoff.

### Job-Based Progress Tracking
Long-running collection jobs create `IngestionJob` + `IngestionJobItem` records. Every item status change is persisted, so progress is visible at all times via API.

### Normalized Schema
Data is stored in 7 normalized tables with proper foreign keys and indexes. This enables efficient analysis queries without duplication.
