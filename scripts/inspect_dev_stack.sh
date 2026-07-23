#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "FlipRadar local URLs"
echo "  Frontend: http://127.0.0.1:5173"
echo "  Backend:  http://127.0.0.1:8000"
echo "  API docs: http://127.0.0.1:8000/docs"
echo "  Postgres: 127.0.0.1:5432"
echo "  Redis:    127.0.0.1:6379"
echo
docker compose ps
echo
docker compose logs --tail=80 backend frontend db redis
