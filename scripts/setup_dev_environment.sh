#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

python3 -m venv backend/venv
backend/venv/bin/python -m pip install --upgrade pip
backend/venv/bin/python -m pip install -r backend/requirements.txt

cd frontend
npm install
