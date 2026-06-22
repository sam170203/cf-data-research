# CF Growth Lab — Roadmap

## Phase 1: Data Collection + Research Infrastructure ✅ (Current)

### Done
- [x] Project scaffold with modern Python tooling
- [x] PostgreSQL schema (7 tables, proper FKs and indexes)
- [x] Alembic migrations
- [x] Codeforces API client with rate limiting and retries
- [x] Single-user data ingestion (profile, rating, submissions)
- [x] Top-100 user collection pipeline with live progress
- [x] Job/Progress tracking system
- [x] Analysis layer (rating milestones, tag distribution, growth rates)
- [x] FastAPI research dashboard (stats, users, jobs, metrics)
- [x] Research readiness scoring
- [x] Documentation

### Remaining Phase 1 Tasks
- [ ] Contest ingestion (scrape all contests + problems)
- [ ] Historic data expansion (users who hit 1200→2000+)
- [ ] Submissions pagination edge cases (rate limits mid-pagination)
- [ ] Docker Compose setup (app + postgres)
- [ ] CI/CD pipeline (lint, typecheck, test)

## Phase 2: Deeper Analysis (Future)

Goal: Answer research questions about growth trajectories.

- Analyze rating trajectories as time series (clustering)
- Identify "breakout" contests (where users jump 100+ rating)
- Topic mastery curves: which tags are solved at which ratings
- Compare growth rates across countries/organizations
- Submission pattern analysis (language choice, time-of-day, solve time)
- Jupyter notebooks with published research findings

## Phase 3: Predictive Models (Future)

Goal: Predict rating outcomes and recommend learning paths.

- Rating projection models (Gaussian processes, Bayesian)
- Next-contest rating change prediction
- Problem difficulty calibration per user
- Personalized weak-topic detection

## Phase 4: AI Coach Integration (Future)

Goal: Power CodeArena's AI Coach with research-backed insights.

- Personalized problem recommendations based on growth trajectory
- Adaptive learning path generation
- Cross-user pattern matching ("users like you improved by...")
- Natural language feedback on contest performance
- Training plan generation

## Design Principles

1. **Data first** — Collect everything before building models.
2. **Reproducibility** — All analysis is scripted, not manual.
3. **Observability** — Always know what's been collected and what's running.
4. **Extensibility** — New data sources and analyses slot in without rewrites.
5. **Production quality** — Type-checked, tested, documented code.
