PYTHON ?= ./venv/bin/python
PYTHON_VERSION := 3.14.2

.PHONY: dev start stop inspect reset setup migrate-seed reset-db reset-demo-data refresh-prices prune-prices snapshot-portfolios quality format format-check backend-quality frontend-quality check-python certify-release-containers

check-python:
	@test "$$($(PYTHON) -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')" = "$(PYTHON_VERSION)" || { echo "Python $(PYTHON_VERSION) is required; run make setup or set PYTHON to that interpreter." >&2; exit 1; }

dev:
	./scripts/run_local_app.sh

start:
	./scripts/start_dev_stack.sh

stop:
	./scripts/stop_dev_stack.sh

inspect:
	./scripts/inspect_dev_stack.sh

reset:
	./scripts/reset_dev_stack.sh

setup:
	./scripts/setup_dev_environment.sh

migrate-seed:
	./scripts/migrate_and_seed.sh

reset-db:
	./scripts/reset_database.sh

reset-demo-data:
	./scripts/reset_database.sh

refresh-prices: check-python
	$(PYTHON) scripts/refresh_price_snapshots.py $(SETS)

prune-prices: check-python
	$(PYTHON) scripts/prune_price_snapshots.py

snapshot-portfolios: check-python
	$(PYTHON) scripts/snapshot_portfolio_valuations.py

quality: check-python
	./scripts/check_quality.sh

format: check-python
	$(PYTHON) -m black backend scripts
	$(PYTHON) -m ruff check --fix backend scripts
	npm run format --prefix frontend

format-check: check-python
	$(PYTHON) -m black --check backend scripts
	$(PYTHON) -m ruff check backend scripts
	npm run format:check --prefix frontend

backend-quality: check-python
	$(PYTHON) -m ruff check backend scripts
	$(PYTHON) -m black --check backend scripts
	$(PYTHON) -m pyright
	$(PYTHON) -m pytest backend/tests

frontend-quality:
	npm run lint --prefix frontend
	npm run format:check --prefix frontend
	npm run typecheck --prefix frontend
	npm run test:coverage --prefix frontend
	npm run build --prefix frontend

certify-release-containers:
	./scripts/verify_release_containers.sh
