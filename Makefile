.PHONY: dev start stop inspect reset setup migrate-seed reset-db refresh-prices prune-prices quality format format-check backend-quality frontend-quality

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

refresh-prices:
	./venv/bin/python scripts/refresh_price_snapshots.py $(SETS)

prune-prices:
	./venv/bin/python scripts/prune_price_snapshots.py

quality:
	./scripts/check_quality.sh

format:
	./venv/bin/python -m black backend scripts
	./venv/bin/python -m ruff check --fix backend scripts
	npm run format --prefix frontend

format-check:
	./venv/bin/python -m black --check backend scripts
	./venv/bin/python -m ruff check backend scripts
	npm run format:check --prefix frontend

backend-quality:
	./venv/bin/python -m ruff check backend scripts
	./venv/bin/python -m black --check backend scripts
	./venv/bin/python -m pyright
	./venv/bin/python -m pytest backend/tests

frontend-quality:
	npm run lint --prefix frontend
	npm run format:check --prefix frontend
	npm run typecheck --prefix frontend
	npm run test:coverage --prefix frontend
	npm run build --prefix frontend
