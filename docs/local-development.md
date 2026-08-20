# Local Development

FlipRadar can run as a complete local stack through Docker Compose. A clean clone does not need manual table creation: the backend service waits for PostgreSQL, runs Alembic migrations, seeds demo data, and then starts Uvicorn.

## Required Tools

- Docker Engine 24 or newer
- Docker Compose v2
- Python 3.14.2 for optional local backend development (the exact version is
  recorded in `.python-version`)
- Node.js 22 or newer for optional local frontend development
- npm 10 or newer

## Local URLs And Ports

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

## One-Command Startup

```bash
./scripts/run_local_app.sh
```

Equivalent Make command:

```bash
make dev
```

This builds images, starts PostgreSQL and Redis, waits for database readiness, runs migrations, seeds demo data, starts the backend, and starts the Vite frontend.

For the seeded account, scenarios, and reset behavior, see [Demo Data](demo-data.md).

## Stack Commands

```bash
./scripts/start_dev_stack.sh
./scripts/stop_dev_stack.sh
./scripts/inspect_dev_stack.sh
./scripts/reset_dev_stack.sh
```

Make aliases:

```bash
make start
make stop
make inspect
make reset
```

## Setup Local Dependencies

Docker does not require local Python or Node dependencies. For editor tooling and local non-Docker commands, run:

```bash
./scripts/setup_dev_environment.sh
```

This creates the repository-root `venv`, installs the pinned backend development
requirements, and runs `npm install` in `frontend`.

## Migrations And Seed Data

Run migrations and seed demo data against the Docker PostgreSQL service:

```bash
./scripts/migrate_and_seed.sh
```

Make alias:

```bash
make migrate-seed
```

The backend container also runs this sequence automatically before starting.

## Database Reset

Resetting deletes local Docker volumes. The script requires typing `RESET` before it proceeds.

```bash
./scripts/reset_database.sh
```

Make alias:

```bash
make reset-db
make reset-demo-data
```

`make reset-demo-data` is the clearest way to start over before a demo. It asks
for confirmation, destroys only the local Docker volumes, rebuilds the database,
and reseeds the stable demo data.

## Services

- `db`: PostgreSQL 16 with `pg_isready` health checks.
- `redis`: Redis 7 with `redis-cli ping` health checks.
- `backend`: FastAPI app with `/db-health` health checks and database startup waiting.
- `frontend`: Vite development server with `/api` proxied to the backend service.
