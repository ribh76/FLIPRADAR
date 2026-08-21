# FlipRadar Backend

The backend is a FastAPI API backed by async SQLAlchemy, Alembic migrations, and PostgreSQL in normal development.

For the complete Docker stack, see [local development](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/local-development.md). For the seeded account and demo scenarios, see [demo data](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/demo-data.md).

## Setup

From the repository root:

```bash
python3.14 -m venv venv
./venv/bin/python -m pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
```

FlipRadar uses Python 3.14.2, recorded in the repository-root `.python-version`.
`requirements.txt` records pinned direct production dependencies and
`requirements.lock` pins their complete resolved graph. Use
`requirements-dev.txt` for local development, tests, and quality tooling.

Required environment variables are documented in `.env.example`. For local development, set at least:

- `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`
- `JWT_SECRET_KEY` with at least 32 characters

`flipradar/core/settings.py` loads environment values from `backend/.env`.

Runtime settings are grouped in `flipradar.core.settings.Settings`. See [docs/runtime-configuration.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/runtime-configuration.md) for supported environments, production validation, and optional integration behavior.

## Run

```bash
cd backend
../venv/bin/python -m uvicorn flipradar.main:create_app --factory --host 127.0.0.1 --port 8000 --reload --no-proxy-headers
```

Shortcut:

```bash
cd backend
../venv/bin/python run.py
```

Swagger UI is available at `http://127.0.0.1:8000/docs`.

## Docker

The backend image is defined in `backend/Dockerfile`. In Docker Compose, the backend waits for PostgreSQL, runs Alembic migrations, seeds demo data, and starts:

```bash
python -m uvicorn flipradar.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --no-proxy-headers
```

The backend health check uses `GET /db-health`.

## Database Migrations

Alembic is configured by `backend/alembic.ini`, with migration files in `backend/flipradar/database/migrations`.

```bash
cd backend
../venv/bin/python -m alembic upgrade head
```

Create a new migration:

```bash
cd backend
../venv/bin/python -m alembic revision --autogenerate -m "describe change"
```

Test migrations against a temporary SQLite database:

```bash
cd backend
ALEMBIC_DATABASE_URL=sqlite:////private/tmp/flipradar_alembic_test.db ../venv/bin/python -m alembic upgrade head
ALEMBIC_DATABASE_URL=sqlite:////private/tmp/flipradar_alembic_test.db ../venv/bin/python -m alembic check
```

## Seed And Utility Scripts

Root scripts add `backend/` to `sys.path`, so run them from the project root:

```bash
./venv/bin/python scripts/create_database_tables.py
./venv/bin/python scripts/seed_database.py
```

The idempotent seed covers catalog sets, multi-date price snapshots, listings,
portfolio holdings, watchlist observations, and a saved portfolio analysis.
Use `./scripts/migrate_and_seed.sh` to apply it; use `make reset-demo-data` to
delete the local Docker data and recreate the full baseline. Keep the locally
seeded demo credentials out of logs, telemetry, and issue reports.

## Tests

```bash
./venv/bin/python -m pytest backend/tests
```

Run a single test file:

```bash
./venv/bin/python -m pytest backend/tests/api/test_api_routes.py
```

Tests are organized by intent:

- `tests/unit/` for isolated business logic and engines.
- `tests/integration/` for database and cross-layer integration.
- `tests/api/` for FastAPI route behavior.

## Quality

From the repository root:

```bash
make backend-quality
```

This runs Ruff import/lint checks, Black formatting checks, Pyright type checking, and pytest. Format backend code with:

```bash
make format
```

## API Overview

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

For how cost basis, estimated value, confidence, freshness, and limitations are
presented, see [the documentation index](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/README.md).
