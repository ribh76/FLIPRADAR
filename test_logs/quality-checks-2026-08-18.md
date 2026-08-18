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

- Vitest emitted a Node experimental warning that `localStorage` is unavailable without `--localstorage-file`.
- Backend pytest emitted a Starlette deprecation warning concerning `httpx` and `TestClient`.
