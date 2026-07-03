# FlipRadar

FlipRadar lets LEGO collectors analyze set decisions, track portfolio value, and look up set details. The backend is a FastAPI + async SQLAlchemy API backed by PostgreSQL.

## V1 Scope

- Auth: register, log in, and inspect the current user.
- Analyze: submit a set number, goal, asking price, and condition to get BUY, PASS, WATCH, SELL, or HOLD guidance from stored snapshots.
- Portfolio: authenticated users can track owned sets, cost basis, estimated current value, and gain/loss.
- Set Detail Lookup: fetch LEGO set metadata and latest stored market snapshot data.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Required environment variables:

- `DATABASE_PASSWORD`
- `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`
- `JWT_SECRET_KEY` for non-local use

## Run

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger UI is available after startup:

```text
http://127.0.0.1:8000/docs
```

Create tables and demo data:

```bash
python3 scripts/create_database_tables.py
python3 scripts/seed_database.py
```

Demo sets include `42071`, `75192`, and `75313`.

## Tests

```bash
python3 -m black .
python3 -m ruff check .
python3 -m pytest
```

Run a single test file:

```bash
python3 -m pytest tests/test_api_routes.py
```

## V1 API Overview

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /analyze`
- `GET /recommendations/{set_number}`
- `GET /portfolio`
- `POST /portfolio/items`
- `DELETE /portfolio/items/{item_id}`
- `GET /portfolio/summary`
- `GET /sets`
- `GET /sets/{set_number}`
- `GET /sets/{set_number}/snapshots/latest`
- `GET /sets/{set_number}/listings`
- `GET /listings/{set_number}`
- `POST /marketplace/update/{set_number}`

Marketplace routes are supporting/internal data refresh helpers for V1, not the primary user workflow.

## Additions On July 2, 2026

- Added V1 auth with `User` persistence, password hashing, JWT access tokens, and `/auth/register`, `/auth/login`, `/auth/me`.
- Added authenticated portfolio tracking with portfolio item persistence, valuation summaries, and missing-market-data handling.
- Added canonical set detail lookup at `GET /sets/{set_number}` with latest snapshot data and valuation status.
- Removed route ambiguity where `GET /sets/{set_number}` previously returned listings; listings now live under explicit listing paths.
- Added canonical recommendation lookup at `GET /recommendations/{set_number}` while keeping the old singular route deprecated.
- Added internal marketplace refresh at `POST /marketplace/update/{set_number}`.
- Added demo seed data for `42071`, `75192`, and `75313`.
- Added auth, portfolio, and set detail test coverage.
- Updated Swagger/OpenAPI tags around the V1 product API.

## Out Of Scope For V1

- Social or community features
- Instagram/community builder flows
- Parts finder
- Saved searches
- Watchlists
- Deal finder pages
- OAuth, roles, email verification, password reset
- Celery/Redis-driven background workflows unless a future V1 need requires them
