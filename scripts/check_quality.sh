#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${BACKEND_PYTHON:-$ROOT_DIR/venv/bin/python}"
REQUIRED_PYTHON_VERSION="3.14.2"

cd "$ROOT_DIR"

if [[ "$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')" != "$REQUIRED_PYTHON_VERSION" ]]; then
  echo "Python $REQUIRED_PYTHON_VERSION is required (set BACKEND_PYTHON to its executable)." >&2
  exit 1
fi

echo "==> Backend Ruff"
"$PYTHON_BIN" -m ruff check backend scripts

echo "==> Backend Black"
"$PYTHON_BIN" -m black --check backend scripts

echo "==> Backend Pyright"
"$PYTHON_BIN" -m pyright

echo "==> Backend pytest"
"$PYTHON_BIN" -m pytest backend/tests

echo "==> Frontend ESLint"
npm run lint --prefix frontend

echo "==> Frontend Prettier"
npm run format:check --prefix frontend

echo "==> Frontend type check"
npm run typecheck --prefix frontend

echo "==> Frontend tests with coverage"
npm run test:coverage --prefix frontend

echo "==> Frontend build"
npm run build --prefix frontend
