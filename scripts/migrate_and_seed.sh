#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

docker compose up -d db redis
docker compose build backend
docker compose run --rm backend bash -lc "python /app/scripts/wait_for_database.py && python -m alembic upgrade head && python /app/scripts/seed_database.py"
