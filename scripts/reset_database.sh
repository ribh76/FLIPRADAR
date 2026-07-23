#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "This will stop the local stack and delete the Docker volumes for Postgres, Redis, and frontend node_modules."
read -r -p "Type RESET to continue: " confirmation

if [[ "$confirmation" != "RESET" ]]; then
  echo "Database reset cancelled."
  exit 0
fi

docker compose down -v --remove-orphans
docker compose up -d db redis
docker compose build backend
docker compose run --rm backend bash -lc "python /app/scripts/wait_for_database.py && python -m alembic upgrade head && python /app/scripts/seed_database.py"

echo "Database reset complete. Run ./scripts/start_dev_stack.sh to start the full app."
