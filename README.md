# Codeforces Mastery Guide

Data-driven research into how competitive programmers improve, visualized in 3D.

## What It Does

Analyzes **325 top Codeforces users** and **1M+ submissions** to answer:

- **What to learn & when** — tag progression from Pupil (1200) to Grandmaster (2400)
- **How experts practice** — habits, difficulty targeting, tag diversity
- **What predicts breakthroughs** — +150/90d, +300/180d, +500 patterns
- **Why people plateau** — warning signs and growth indicators
- **Coder archetypes** — KMeans clustering of practice styles

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.14, FastAPI, asyncpg, SQLAlchemy |
| Frontend | Next.js 15, Three.js, Tailwind CSS |
| Analysis | scikit-learn, XGBoost, HDBSCAN, NumPy |
| Database | PostgreSQL |
| 3D | Three.js with OrbitControls, CSS2DRenderer |

## Getting Started

### Backend

```bash
uv sync
uv run uvicorn app.api.main:app --reload
```

### Frontend

```bash
cd client
npm install
npm run dev
```

### Database

```bash
# Start PostgreSQL, then:
uv run python scripts/create_schema.py
```

## Project Structure

```
├── app/                    # FastAPI backend
│   ├── api/routes/         # REST endpoints
│   ├── research/           # Analysis modules
│   ├── models/             # SQLAlchemy models
│   └── services/           # Data ingestion, cache
├── client/                 # Next.js frontend
│   └── app/
│       ├── (main)/         # Sidebar pages
│       │   ├── page.tsx            # Home dashboard
│       │   ├── breakthroughs/      # Breakthrough analysis
│       │   ├── plateaus/           # Plateau patterns
│       │   ├── expert-pathways/    # Tag progression
│       │   └── ...
│       └── 3d/             # Full-screen Three.js 3D dashboard
│           └── page.tsx
├── scrapers/               # Codeforces API ingestion
├── analysis/               # Standalone analysis scripts
├── alembic/                # Database migrations
└── docs/                   # Architecture docs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/metrics` | User/submission stats |
| `/research/expert-pathways` | Tag progression per rating |
| `/research/breakthrough-plateau` | Breakthrough & plateau analysis |
| `/research/clusters` | Coder archetype clusters |
| `/research/trajectories/questions` | Per-user timeline Q&A |
| `/3d-dashboard` | Pre-computed data for 3D viz |

## 3D Dashboard

Navigate to `/3d` for an interactive 3D visualization of the path to Grandmaster:

- **6 milestone platforms** (1200→2400)
- **Orbiting tag spheres** — click any tag to learn when experts master it
- **Floating particles** — ambient skill activity
- **Breakthrough bursts** — orbiting particle clusters
- **Orbit controls** — drag to rotate, scroll to zoom

## Key Findings

1. **Tag progression is consistent**: brute force → math → greedy → implementation (low rating) → dfs → graphs → dp → trees (mid) → flows → FFT → string structures (high)
2. **Experts practice above their level**: ~1470 difficulty while rated below 1400
3. **Breakthroughs follow sustained effort**: ~308 problems in 6 months before a +150 gain
4. **Plateaus come from comfort zones**: lower difficulty, fewer tags, less practice
