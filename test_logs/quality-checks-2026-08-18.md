# Quality Check Baseline — 2026-08-18

This is the pre-debugging baseline required by the production-readiness plan.
No application-code fixes were made before these checks ran.

## Environment

| Tool | Version |
| --- | --- |
| Python | 3.14.2 |
| Node.js | 26.3.0 |
| npm | 11.16.0 |

## Backend

| Check | Command | Status | Result |
| --- | --- | --- | --- |
| Ruff | `./venv/bin/python -m ruff check backend scripts` | Failed | 8 violations: 7 auto-fixable import-order violations, 2 unused imports, and 1 `UP047` generic-function violation. |
| Black | `./venv/bin/python -m black --check backend scripts` | Failed | 28 files would be reformatted. |
| Pyright | `./venv/bin/python -m pyright` | Failed | 77 errors, 0 warnings, 0 informational messages. |
| pytest | `./venv/bin/python -m pytest backend/tests -q --tb=short` | Failed | 215 passed, 87 failed, 1 warning; 302 tests total; completed in 29.06 seconds. |

## Frontend

| Check | Command | Status | Result |
| --- | --- | --- | --- |
| ESLint | `npm run lint --prefix frontend` | Passed | Exit code 0. |
| Prettier | `npm run format:check --prefix frontend` | Failed | Formatting issues in 17 files. |
| TypeScript | `npm run typecheck --prefix frontend` | Passed | Exit code 0. |
| Vitest with coverage | `npm run test:coverage --prefix frontend` | Failed coverage gate | 15 test files and 50 tests passed. Coverage was 37.71% statements, 60% branches, 19.56% functions, and 37.57% lines; it missed the global thresholds of 75% statements/functions/lines and 70% branches. |
| Production build | `npm run build --prefix frontend` | Passed | TypeScript build and Vite production build completed successfully. |

## Notes

## Known Failures from the First Run

### Dependency and environment failures

- `argon2-cffi` is not installed in the active `venv`. Passlib therefore raised `passlib.exc.MissingBackendError` in 60 backend tests. This cascades through registration, login, password reset, session, account-settings, and other authenticated API tests.
- The test process ran with the application environment set to `test`, release set to `unknown`, and eBay, BrickLink, email, and Anthropic integrations disabled because they were not configured. Those integrations are expected to remain disabled in this baseline; no live external services were called.

### Backend test and contract failures

- Snapshot API tests frequently received `422 Unprocessable Entity` responses where the tests expected successful responses. The logged validation failures concern snapshot request data, including marketplace and condition values.
- Several catalog, portfolio, watchlist, saved-search, notification, pricing, recommendation, and set-detail API tests failed after the initial snapshot/authentication failures. Their exact test names are retained in the pytest console output from this run; this baseline groups them to avoid treating cascades as independent root causes.
- The database-ingestion suite has assertion mismatches for normalized listing/snapshot data and price-snapshot fields.
- `test_dashboard_read_reuses_one_valuation_pass_and_handles_missing_history` failed in the portfolio-valuation integration suite.
- `test_portfolio_analysis_derives_labels_before_calling_llm` failed because its mocked `refresh` function does not accept the production call's `portfolio_id` keyword argument.

### Static-quality failures

- Ruff reported 8 violations: 5 import-order violations, 2 unused imports, and 1 `UP047` generic-function modernization issue.
- Black reported 28 files that would be reformatted.
- Pyright reported 77 errors. The reported categories include invalid `Literal` type expressions, optional values passed where concrete values are required, SQLAlchemy result typing, dictionary key invariance, and test double/type mismatches.
- Frontend Prettier reported formatting issues in 17 files.
- Frontend coverage gates failed even though all Vitest assertions passed. The first-run coverage result is 37.71% statements, 60% branches, 19.56% functions, and 37.57% lines, below the configured global thresholds of 75%, 70%, 75%, and 75% respectively.

## Skipped, Expected-Failure, and Warning Inventory

- **Skipped tests:** none reported by backend pytest or frontend Vitest.
- **Expected failures / unexpected passes:** none reported.
- **Backend test warning:** Starlette warns that `fastapi.testclient` uses a deprecated `httpx`/`TestClient` path and recommends `httpx2`.
- **Frontend test warning:** Node emitted an experimental warning that `localStorage` is unavailable without `--localstorage-file`.
- **Application log warnings during backend tests:** expected validation-error, insufficient-valuation-data, and disabled-integration warnings appeared in the captured test output. They are recorded as baseline noise only; they did not create additional pytest warning-summary entries.

## Environment-Specific Behavior

- This baseline used Python 3.14.2 and Node.js 26.3.0. The Dockerfiles specify Python 3.13 and Node.js 22 respectively, so future Docker/CI results may differ from this local baseline.
- The active virtual environment lacks the Argon2 backend required by Passlib. Re-running after installing dependencies from `backend/requirements.txt` should confirm whether the 60 authentication-related failures are environmental rather than application defects.
- Test-only startup deliberately disables unconfigured third-party integrations; resulting warning logs and mock-provider behavior are not production-service failures.
