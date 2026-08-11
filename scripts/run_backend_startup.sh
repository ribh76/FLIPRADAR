#!/usr/bin/env bash
set -Eeuo pipefail

stage="database_wait"
report_failure() {
  python /app/scripts/report_operational_failure.py "$stage" || true
}
trap report_failure ERR

python /app/scripts/wait_for_database.py
stage="migration"
python -m alembic upgrade head
stage="seed"
python /app/scripts/seed_database.py
