# FlipRadar

FlipRadar is a LEGO collecting and resale analysis app. It combines a FastAPI backend, a React/Vite frontend, pricing and recommendation engines, marketplace integrations, and planning documentation for the product roadmap.

## Project Structure

- `backend/` - FastAPI app, SQLAlchemy models, services, engines, integrations, Alembic migrations, backend tests, and Python dependency files.
- `frontend/` - React, TypeScript, Vite, Tailwind, static assets, and frontend build configuration.
- `docs/` - Product roadmap, UML/mockups, architecture notes, API/database references, and deployment planning.
- `scripts/` - Root-level helper scripts for setup, seed data, migrations, and automation tasks.
- `.github/` - GitHub Actions and repository automation configuration.

## Main Workflows

Backend setup and commands live in [backend/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/backend/README.md).

Frontend setup and commands live in [frontend/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/frontend/README.md).

Documentation is indexed in [docs/README.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/README.md).

Local Docker development is documented in [docs/local-development.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/local-development.md).

Runtime configuration is documented in [docs/runtime-configuration.md](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/runtime-configuration.md).

## Local Development

Start the API:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn flipradar.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

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

## Product Scope

The current V1 direction includes account auth, LEGO set lookup, stored market snapshots, buy/pass/watch/hold/sell guidance, portfolio tracking, and set detail views. The full roadmap is maintained in [docs/TODOs.txt](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/TODOs.txt).
