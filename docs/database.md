# Database Design

## Entity-Relationship Overview

```
┌─────────────┐       ┌──────────────────┐       ┌──────────────┐
│    users    │1───N→│  rating_history  │       │  contests   │
└─────────────┘       └──────────────────┘       └──────┬───────┘
      1                                                  │
      │                                                  │1
      │                                                  │
      ▼                                                  ▼
┌─────────────┘       ┌──────────────────┐       ┌──────────────┐
│  submissions  │     │   problems      │N───1│  contests    │
└──────────────┘       └──────────────────┘       └──────────────┘

┌──────────────────┐       ┌────────────────────────┐
│  ingestion_jobs  │1───N→│  ingestion_job_items   │
└──────────────────┘       └────────────────────────┘
```

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | PK |
| cf_handle | VARCHAR(64) | UNIQUE, INDEXED |
| current_rating | INTEGER | Nullable (unrated users) |
| max_rating | INTEGER | |
| rank | VARCHAR(32) | e.g. "expert", "grandmaster" |
| max_rank | VARCHAR(32) | |
| country | VARCHAR(128) | |
| city | VARCHAR(128) | |
| organization | VARCHAR(256) | |
| contribution | INTEGER | |
| friend_of_count | INTEGER | |
| last_online_time | TIMESTAMPTZ | |
| registration_time | TIMESTAMPTZ | |
| first_seen_at | TIMESTAMPTZ | Auto-set on first insert |
| updated_at | TIMESTAMPTZ | Auto-updated |

### rating_history
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | PK |
| user_id | INTEGER | FK → users.id, INDEXED |
| contest_id | INTEGER | |
| contest_name | VARCHAR(256) | |
| old_rating | INTEGER | |
| new_rating | INTEGER | |
| rating_change | INTEGER | |
| rank | INTEGER | Contest rank |
| contest_time | TIMESTAMPTZ | |

### contests
| Column | Type | Notes |
|--------|------|-------|
| contest_id | INTEGER | PK (CF contest ID) |
| name | VARCHAR(256) | |
| type | VARCHAR(32) | CF, ICPC, etc. |
| phase | VARCHAR(32) | BEFORE, CODING, FINISHED |
| start_time | TIMESTAMPTZ | |
| duration | INTEGER | Seconds |
| prepared_by | VARCHAR(128) | |
| difficulty | VARCHAR(32) | |
| kind | VARCHAR(64) | |
| country | VARCHAR(128) | |
| season | VARCHAR(32) | |
| description | TEXT | |

### problems
| Column | Type | Notes |
|--------|------|-------|
| contest_id | INTEGER | FK → contests.contest_id |
| index | VARCHAR(8) | e.g. "A", "B", "C" |
| name | VARCHAR(256) | |
| rating | INTEGER | Problem difficulty rating |
| tags | TEXT[] | Array of tag strings |
| solved_count | INTEGER | |
| PK | (contest_id, index) | Composite primary key |

### submissions
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT | PK (CF submission ID) |
| user_id | INTEGER | FK → users.id, INDEXED |
| contest_id | INTEGER | |
| problem_index | VARCHAR(8) | |
| problem_name | VARCHAR(256) | |
| problem_rating | INTEGER | |
| problem_tags | TEXT[] | |
| verdict | VARCHAR(32) | OK, WRONG_ANSWER, etc. |
| programming_language | VARCHAR(64) | |
| submission_time | TIMESTAMPTZ | |

### ingestion_jobs
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | PK |
| job_type | VARCHAR(64) | e.g. "top_users_collection" |
| status | VARCHAR(16) | pending/running/completed/failed |
| total_items | INTEGER | |
| completed_items | INTEGER | |
| failed_items | INTEGER | |
| started_at | TIMESTAMPTZ | |
| finished_at | TIMESTAMPTZ | |

### ingestion_job_items
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | PK |
| job_id | INTEGER | FK → ingestion_jobs.id, INDEXED |
| item_identifier | VARCHAR(128) | e.g. CF handle |
| status | VARCHAR(16) | pending/running/completed/failed |
| error_message | TEXT | |

## Indexes

- `users.cf_handle` — UNIQUE index for handle lookups
- `rating_history.user_id` — Fast user-specific history queries
- `submissions.user_id` — Fast user-specific submission queries
- `ingestion_jobs.job_type` — Filter jobs by type
- `ingestion_job_items.job_id` — Fast item lookup by job
