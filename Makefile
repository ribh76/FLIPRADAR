.PHONY: dev start stop inspect reset setup migrate-seed reset-db

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
