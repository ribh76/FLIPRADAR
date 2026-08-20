# FlipRadar

FlipRadar is a LEGO collecting and resale analysis app. It combines a FastAPI backend, a React/Vite frontend, pricing and recommendation engines, marketplace integrations, and a repeatable local demo.

## Project Structure

- `backend/` - FastAPI app, SQLAlchemy models, services, engines, integrations, Alembic migrations, backend tests, and Python dependency files.
- `frontend/` - React, TypeScript, Vite, Tailwind, static assets, and frontend build configuration.
- `docs/` - Product, architecture, valuation, data-limit, demo, and local-development references.
- `scripts/` - Root-level helper scripts for setup, seed data, migrations, and automation tasks.
- `.github/` - GitHub Actions and repository automation configuration.

## Main Workflows

Backend setup and commands live in [backend/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/backend/README.md).

Frontend setup and commands live in [frontend/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/frontend/README.md).

Documentation is indexed in [docs/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/README.md).

Local Docker development is documented in [docs/local-development.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/local-development.md).

Runtime configuration is documented in [docs/runtime-configuration.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/runtime-configuration.md).

Run the complete local quality gate before CI integration:

```bash
make quality
```

That command runs backend formatting checks, Ruff, Pyright, pytest, frontend ESLint, TypeScript checks, Vitest coverage, and the production frontend build.

## Merge Requirements

The `main` branch protection policy requires changes to be delivered through a
pull request; direct pushes and force pushes are not permitted.

Before GitHub allows a pull request to merge, its branch must be up to date
with `main`, free of merge conflicts, and have all of these checks passing:

- `Backend CI`
- `Frontend CI`
- `Database migrations`
- `Build backend production image`
- `Build frontend production image`

If GitHub marks a required check as stale after `main` advances, update the
pull-request branch and wait for the checks to run again before merging.

## Local Development

Start the API:

```bash
python3.14 -m venv venv
./venv/bin/python -m pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
cd backend
../venv/bin/python -m uvicorn flipradar.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

The backend runtime is Python 3.14.2. `.python-version` records it for local
version managers; Docker, CI, and Make targets use the same pin.

Start the complete Docker stack:

```bash
./scripts/run_local_app.sh
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000`.

## Demo

The Docker stack automatically migrates and seeds representative local data.
Use the controlled local demo credentials without copying them into telemetry.
The seeded data includes catalog sets, price trends, listings, a portfolio,
watchlist observations, and a saved analysis. See [Demo Data](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/demo-data.md) for scenarios and reset instructions.

To rebuild the disposable local demo baseline, run `make reset-demo-data` and
confirm with `RESET`.

## Product Scope

The current V1 direction includes account auth, LEGO set lookup, stored market snapshots, buy/pass/watch/hold/sell guidance, portfolio tracking, and set detail views. The full roadmap is maintained in [docs/TODOs.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/TODOs.md).
