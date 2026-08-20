#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PYTHON_BIN="${PYTHON_BIN:-python3.14}"
REQUIRED_PYTHON_VERSION="3.14.2"
PIP_VERSION="25.3"

if [[ "$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')" != "$REQUIRED_PYTHON_VERSION" ]]; then
  echo "Python $REQUIRED_PYTHON_VERSION is required (set PYTHON_BIN to its executable)." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv venv
venv/bin/python -m pip install --upgrade "pip==$PIP_VERSION"
venv/bin/python -m pip install -r backend/requirements-dev.txt

cd frontend
npm install
