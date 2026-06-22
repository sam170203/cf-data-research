# Data Ingestion Flow

## Overview

Data ingestion pulls user profiles, rating histories, and submissions from the Codeforces API and stores them in PostgreSQL. The system is designed for reliability with rate limiting, retries, and job progress tracking.

## API Endpoints Used

| CF API | Endpoint | Purpose |
|--------|----------|---------|
| `user.info` | `/api/user.info?handles={handle}` | Profile, rating, rank |
| `user.rating` | `/api/user.rating?handle={handle}` | Rating change history |
| `user.status` | `/api/user.status?handle={handle}&from=1&count=1000` | Submissions (paginated) |
| `user.ratedList` | `/api/user.ratedList?activeOnly=true` | List of all rated users |
| `contest.list` | `/api/contest.list?gym=false` | Contest metadata |
| `problemset.problems` | `/api/problemset.problems` | Problem catalog |

## Rate Limiting

The Codeforces API enforces approximately 1 request per second. The `RateLimiter` class in `app/services/codeforces.py` ensures compliance:

```python
limiter = RateLimiter(requests_per_second=1.0)
await limiter.acquire()  # blocks until slot available
```

## Retry Logic

Transient failures (HTTP 503, timeouts) trigger exponential backoff:

- Attempt 1: immediate
- Attempt 2: wait 2s
- Attempt 3 (last): wait 4s

Permanent errors (404, 400, etc.) fail immediately.

## Ingestion Flow

### Single User Ingestion

```
1. fetch_user_profile(handle)      → upsert users table
2. fetch_rating_history(handle)    → insert rating_history rows
3. fetch_all_submissions(handle)   → insert submissions rows (paginated)
```

Each step is idempotent — duplicate entries are detected and skipped.

### Bulk Collection

```
1. Fetch top N handles from /user.ratedList
2. Create IngestionJob record (status=pending)
3. Create IngestionJobItem per handle
4. For each handle sequentially:
   a. Mark item as running
   b. Call single-user ingestion
   c. Mark item completed (or failed with error)
   d. Print progress to terminal
5. Mark job as completed
```

## Job Types

| job_type | Description |
|----------|-------------|
| `top_users_collection` | Collect top N users by rating |
| `user_ingestion` | Collect a single user's data |

## Progress Tracking

While a collection runs, progress is displayed in the terminal:

```
[1/100] tourist ✓ (8500 subs, 150 contests)
  Progress: 1%  ETA: 45m remaining  (1 ok, 0 failed)
```

The same data is available via API:

```
GET /jobs/{job_id}
→ { job_id, status, total_items, completed_items,
    failed_items, progress_percent }
```

## CLI Commands

### Collect Top Users

```bash
# Basic: collect top 100 users by rating
python -m scrapers.jobs.collect_top_users

# Custom count
python -m scrapers.jobs.collect_top_users --count 200

# Include historic top users (tourist, Petr, etc.)
python -m scrapers.jobs.collect_top_users --historic
```

### Ingest Single User

```bash
python -m scrapers.jobs.ingest_user tourist
```
