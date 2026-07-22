# FlipRadar Backend

The backend is a FastAPI API backed by async SQLAlchemy, Alembic migrations, and PostgreSQL in normal development.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Required environment variables are documented in `.env.example`. For local development, set at least:

- `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`
- `JWT_SECRET_KEY` with at least 32 characters

`config.py` loads environment values from `backend/.env`.

## Run

```bash
cd backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Shortcut:

```bash
cd backend
python3 run.py
```

Swagger UI is available at `http://127.0.0.1:8000/docs`.

## Database Migrations

Alembic is configured by `backend/alembic.ini`, with migration files in `backend/database/migrations`.

```bash
cd backend
source venv/bin/activate
python3 -m alembic upgrade head
```

Create a new migration:

```bash
cd backend
python3 -m alembic revision --autogenerate -m "describe change"
```

Test migrations against a temporary SQLite database:

```bash
cd backend
ALEMBIC_DATABASE_URL=sqlite:////private/tmp/flipradar_alembic_test.db python3 -m alembic upgrade head
ALEMBIC_DATABASE_URL=sqlite:////private/tmp/flipradar_alembic_test.db python3 -m alembic check
```

## Seed And Utility Scripts

Root scripts add `backend/` to `sys.path`, so run them from the project root:

```bash
python3 scripts/create_database_tables.py
python3 scripts/seed_database.py
```

Demo sets include `42071`, `75192`, and `75313`.

## Tests

```bash
cd backend
source venv/bin/activate
python3 -m pytest
```

Run a single test file:

```bash
cd backend
python3 -m pytest tests/test_api_routes.py
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
