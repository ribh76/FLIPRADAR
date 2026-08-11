#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

stage="database_wait"
report_failure() {
  python3 scripts/report_operational_failure.py "$stage" || true
}
trap report_failure ERR

docker compose up -d db redis
docker compose build backend
stage="deployment"
docker compose run --rm backend bash -lc "/app/scripts/run_backend_startup.sh"
