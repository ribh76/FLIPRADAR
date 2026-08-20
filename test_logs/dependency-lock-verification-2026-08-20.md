# Clean Dependency Lock Verification — 2026-08-20

## Scope and environment

- Repository: `FlipRadar`
- Python: 3.14.2
- Node.js: 26.3.0
- npm: 11.16.0
- Backend runtime lock: `backend/requirements.lock`
- Frontend lock: `frontend/package-lock.json` (lockfile version 3)
- Dependency caches: fresh temporary Python virtual environment and npm cache
  under `/private/tmp/flipradar-dependency-verification.r83ASH`

## Clean installation and build results

| Check | Command | Result |
| --- | --- | --- |
| Backend dependency install | `python3.14 -m venv <temp>/backend-venv`; `<temp>/backend-venv/bin/python -m pip install --no-cache-dir -r backend/requirements-dev.txt` | Passed. The environment installed the pinned production lock plus pinned development tools. |
| Backend dependency validation | `<temp>/backend-venv/bin/python -m pip check` | Passed: no broken requirements. |
| Backend build validation | `<temp>/backend-venv/bin/python -m compileall -q backend scripts` | Passed. |
| Frontend clean install | `npm ci --cache <temp>/npm-cache` | Passed: 378 packages installed exclusively from `package-lock.json`. |
| Frontend production build | `npm run build` | Passed: TypeScript build and Vite production build completed. |
| Frontend test suite | `npm test` | Passed: 15 files and 50 tests passed. |
| Backend test suite | `<temp>/backend-venv/bin/python -m pytest backend/tests --tb=short` | Failed: 303 passed, 41 failed, 5 warnings (344 total). |

`npm ci` reported six high-severity audit findings and two dependencies with
pending install-script approval (`esbuild` and `fsevents`). These are warnings
from npm; they did not prevent the lockfile install, frontend tests, or build.

## Backend test failures

The failures below were reproduced in the clean Python 3.14.2 environment with
the locked production dependency graph. They are application behavior, test
fixture, or external-provider configuration failures—not dependency-resolution
errors.

- `backend.tests.api.test_api_routes::test_get_set_endpoint_with_snapshot_does_not_crash` — `TypeError: 'NoneType' object is not subscriptable`
- `backend.tests.api.test_api_routes::test_marketplace_update_returns_provider_error_response` — expected HTTP 502; received 503.
- `backend.tests.api.test_api_routes::test_marketplace_update_returns_provider_timeout_response` — expected HTTP 504; received 503.
- `backend.tests.api.test_api_routes::test_set_search_supports_partial_local_lookup_and_provider_hydration` — expected HTTP 200; received 503.
- `backend.tests.api.test_api_routes::test_set_search_returns_not_found_and_incomplete_provider_errors` — expected HTTP 404; received 503.
- `backend.tests.api.test_api_routes::test_part_search_hydrates_catalog_and_uses_local_results` — expected HTTP 200; received 503.
- `backend.tests.api.test_api_routes::test_listing_evaluation_uses_provider_data_and_deduplicates_recent_requests` — `listing_service.evaluate_listing_url` is missing.
- `backend.tests.api.test_api_routes::test_listing_evaluation_allows_manual_fallback_when_provider_fails` — `listing_service.evaluate_listing_url` is missing.
- `backend.tests.api.test_api_routes::test_listing_evaluation_rejects_private_and_unsupported_urls` — `listing_service.evaluate_listing_url` is missing.
- `backend.tests.api.test_api_routes::test_create_snapshot_endpoint` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_duplicate_snapshot_returns_conflict` — snapshot creation received HTTP 422 instead of 201.
- `backend.tests.api.test_api_routes::test_snapshots_by_set_endpoint` — snapshot collection assertion failed.
- `backend.tests.api.test_api_routes::test_snapshots_by_set_endpoint_supports_pagination_and_filters` — snapshot creation received HTTP 422 instead of 201.
- `backend.tests.api.test_api_routes::test_latest_snapshot_endpoint` — expected HTTP 200; received 404.
- `backend.tests.api.test_api_routes::test_set_number_marketplace_and_condition_values_are_normalized` — request validation rejects `used` as a condition value.
- `backend.tests.api.test_api_routes::test_portfolio_add_list_summary_delete` — expected valuation status `valued`; received `missing_market_data`.
- `backend.tests.api.test_api_routes::test_portfolio_update_item_with_patch_and_put` — expected updated purchase price; received `None`.
- `backend.tests.api.test_api_routes::test_portfolio_summary_handles_quantities_prices_and_conditions` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_set_detail_returns_metadata_and_latest_snapshot` — `TypeError: 'NoneType' object is not subscriptable`.
- `backend.tests.api.test_api_routes::test_set_detail_missing_snapshot_returns_null_valuation` — expected `missing_market_data`; received `provider_unavailable`.
- `backend.tests.api.test_api_routes::test_set_detail_missing_set_returns_404` — expected HTTP 404; received 503.
- `backend.tests.api.test_api_routes::test_analyze_endpoint` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_post_analyze_returns_buy_when_asking_price_is_below_fair_value` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_post_analyze_returns_pass_when_asking_price_is_above_fair_value` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_analyze_endpoint_accepts_buy_goal` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_analyze_endpoint_without_snapshots_returns_low_confidence` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_analyze_endpoint_allows_sell_without_asking_price` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_post_analyze_returns_low_confidence_result_when_no_snapshots_exist` — expected HTTP 201; received 422.
- `backend.tests.api.test_api_routes::test_post_analyze_saves_recommendation_to_db` — expected HTTP 200; received 404.
- `backend.tests.api.test_api_routes::test_analyze_endpoint_calls_engine_pipeline_in_order` — test stub does not accept the `condition` keyword argument.
- `backend.tests.api.test_api_routes::test_get_recommendation_endpoint` — expected HTTP 200; received 404.
- `backend.tests.integration.test_database_ingestion::test_insert_price_snapshot_and_fetch_latest_by_set_number` — `low_price` is not a valid `PriceSnapshot` constructor argument.
- `backend.tests.integration.test_database_ingestion::test_repository_functions_fetch_snapshots_and_create_recommendation` — `median_price` is not a valid `PriceSnapshot` constructor argument.
- `backend.tests.integration.test_database_ingestion::test_listing_normalizer_handles_marketplace_payload_shapes` — normalized listing result differs from the fixture expectation.
- `backend.tests.integration.test_database_ingestion::test_marketplace_service_updates_listings_and_snapshot` — no marketplace provider is enabled and configured.
- `backend.tests.integration.test_database_ingestion::test_portfolio_summary_batches_snapshot_queries` — `median_price` is not a valid `PriceSnapshot` constructor argument.
- `backend.tests.integration.test_part_catalog_service::test_part_catalog_sync_merges_duplicate_parts_and_keeps_color_elements` — BrickLink catalog provider credentials are unavailable.
- `backend.tests.integration.test_part_catalog_service::test_catalog_refresh_replaces_quality_flags_when_provider_data_improves` — BrickLink catalog provider credentials are unavailable.
- `backend.tests.integration.test_part_catalog_service::test_part_lookup_supports_exact_text_fuzzy_and_catalog_filters` — BrickLink catalog provider credentials are unavailable.
- `backend.tests.integration.test_portfolio_valuation_snapshots::test_dashboard_read_reuses_one_valuation_pass_and_handles_missing_history` — `get_portfolio_dashboard()` now requires the `portfolio_id` keyword-only argument.
- `backend.tests.unit.test_llm_portfolio_analysis_service::test_portfolio_analysis_derives_labels_before_calling_llm` — test double does not accept the `portfolio_id` keyword argument.

## Non-failing warnings

- FastAPI/Starlette reports use of the deprecated `httpx` TestClient integration.
- Passlib reports that reading `argon2.__version__` is deprecated.
- Several CSV validation tests use the deprecated Starlette 422 status constant.
