# Production Configuration Contract

This is the authoritative production environment-variable contract for
FlipRadar. Set backend variables in the API and worker deployment environment;
set `VITE_*` variables at the frontend build step. `backend/.env.example` and
`frontend/.env.example` are local-development templates only and never contain
production credentials.

`APP_RELEASE` and `VITE_APP_RELEASE` must be the same immutable release ID
(normally the full Git commit SHA). The production web origin is
`https://app.flipradar.com`; do not substitute a wildcard, localhost, or a
staging URL.

## Installation rules

- Store every value marked **secret** in the deployment platform's production
  secret store. In GitHub Actions, use the protected `production` Environment;
  never repository-wide secrets and never frontend `VITE_*` variables.
- Set all non-secret values as production environment variables. A deployment
  must fail closed if a required value is absent or invalid.
- `backend/.env` is ignored by Git and may mirror this contract for an
  operator-managed deployment. It is not a substitute for the platform secret
  store. Do not commit it.
- Generate `JWT_SECRET_KEY` with `python -c 'import secrets; print(secrets.token_urlsafe(64))'`.
  It must be unique to production, at least 64 characters, and rotated by
  replacing the secret-store value and redeploying all API and worker instances.

## Backend contract

| Group | Variables | Production value / requirement |
| --- | --- | --- |
| Application | `APP_NAME` | `FlipRadar` |
| Application | `APP_ENV`, `APP_DEBUG` | `production`, `false` |
| Application | `FRONTEND_URL` | `https://app.flipradar.com` |
| Release | `APP_RELEASE` | Immutable release ID, e.g. Git commit SHA; never `unknown` |
| Logging | `LOG_LEVEL`, `SQLALCHEMY_LOG_LEVEL`, `UVICORN_ACCESS_LOG_LEVEL` | `INFO`, `WARNING`, `INFO` unless incident response requires otherwise |
| Monitoring | `SENTRY_DSN` | **secret**, optional; production Sentry DSN |
| Monitoring | `ERROR_RATE_ALERT_THRESHOLD_PERCENT`, `ERROR_RATE_ALERT_MINIMUM_REQUESTS`, `ERROR_RATE_ALERT_WINDOW_SECONDS` | `5`, `20`, `300` (tune with an on-call owner) |
| Proxy | `TRUSTED_PROXY_CIDRS` | Private CIDRs of only the terminating proxy; empty when there is none |
| PostgreSQL | `DATABASE_URL` | **secret** external-provider URL with username/password; `postgresql+asyncpg://...` preferred |
| PostgreSQL | `ALEMBIC_DATABASE_URL` | **secret**, optional separate migration URL; same TLS/credential rules as `DATABASE_URL` |
| PostgreSQL | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` | Alternative to `DATABASE_URL`; host must be external and password is **secret** |
| PostgreSQL | `DATABASE_SSL_MODE` | `verify-full` when the provider CA is available; otherwise `require`. Never `prefer` or `disable` |
| PostgreSQL | `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_WAIT_TIMEOUT` | Start with `5`, `10`, `60`; size within provider connection limits |
| Authentication | `JWT_SECRET_KEY` | **secret**, generated as described above; never a default, placeholder, or development value |
| Authentication | `JWT_ALGORITHM` | `HS256` |
| Authentication | `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | `15`, `30` |
| Authentication | `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`, `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, `MFA_TOKEN_EXPIRE_MINUTES` | `30`, `15`, `60` |
| Authentication | `MFA_MAX_ATTEMPTS`, `ACCOUNT_TOKEN_RESEND_COOLDOWN_SECONDS`, `PASSWORD_MIN_LENGTH` | `5`, `300`, `8` or stricter |
| Operations | `OPERATIONAL_ROUTE_USERNAME`, `OPERATIONAL_ROUTE_PASSWORD` | Do not set in public production; internal routes are excluded by production policy |
| Email | `EMAIL_ENABLED`, `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS` | Enable only after provider validation; approved sender address |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME` | Provider endpoint, port, and account identity |
| Email | `SMTP_PASSWORD`, `AUTH_EMAIL_APP_PASSWORD` | **secret**; set one only, with `AUTH_EMAIL_APP_PASSWORD` preferred |
| Email | `EMAIL_TIMEOUT_SECONDS` | `10` |
| eBay | `EBAY_API_ENABLED` | `false` until real credentials and launch approval exist; `true` only when all following credentials are supplied |
| eBay | `EBAY_API_CONFIGURED` | Backward-compatible flag; credentials are authoritative |
| eBay | `EBAY_API_KEY`, `EBAY_API_SECRET` | **secret** when enabled |
| eBay | `EBAY_API_TIMEOUT_SECONDS` | `10` |
| BrickLink | `BRICKLINK_API_ENABLED` | `false` until real credentials and launch approval exist; `true` only when all following credentials are supplied |
| BrickLink | `BRICKLINK_API_CONFIGURED` | Backward-compatible flag; credentials are authoritative |
| BrickLink | `BRICKLINK_CONSUMER_KEY`, `BRICKLINK_CONSUMER_SECRET`, `BRICKLINK_TOKEN_VALUE`, `BRICKLINK_TOKEN_SECRET` | **secret** when enabled |
| BrickLink | `BRICKLINK_API_TIMEOUT_SECONDS` | `10` |
| Provider safety | `ALLOW_MOCK_MARKETPLACE_PROVIDERS` | `false` |
| Pricing | `PRICING_CURRENCY`, `PRICING_FRESHNESS_HOURS`, `PRICING_RETENTION_DAYS`, `PORTFOLIO_VALUATION_RETENTION_DAYS` | `USD`, `24`, `180`, `180` (adjust retention intentionally) |
| LLM | `LLM_ENABLED`, `LLM_PROVIDER`, `ANTHROPIC_API_KEY` | `false` unless approved; provider `anthropic`; API key is **secret** when enabled |
| LLM | `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`, `LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF_SECONDS` | Approved model and bounded values; start with `claude-sonnet-4-6`, `30`, `1500`, `2`, `0.25` |
| LLM | `LLM_USER_RATE_LIMIT`, `LLM_GLOBAL_RATE_LIMIT`, `LLM_RATE_LIMIT_WINDOW_SECONDS` | `10`, `100`, `60`; revise with cost controls |
| LLM | `LLM_INPUT_COST_PER_MILLION_TOKENS`, `LLM_OUTPUT_COST_PER_MILLION_TOKENS` | Current published model prices; review at model changes |
| Redis / Celery | `REDIS_URL` | **secret** `rediss://` external-provider URL including its password; TLS is mandatory |
| Redis / Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | **secret**, optional overrides; `rediss://` external-provider URLs including passwords. Omit to inherit `REDIS_URL` |
| Workers | `WATCHLIST_WORKER_ENABLED`, `WATCHLIST_PROVIDER_HOURLY_LIMIT` | `false` until workers are deployed and monitored; `60` as initial cap |
| CORS | `CORS_ALLOWED_ORIGINS` | Exactly `https://app.flipradar.com`; comma-separated additional approved HTTPS origins only |
| CORS | `CORS_ALLOW_CREDENTIALS` | `true` |
| CORS | `CORS_ALLOW_METHODS` | `GET,POST,PUT,PATCH,DELETE,OPTIONS` |
| CORS | `CORS_ALLOW_HEADERS` | `Authorization,Content-Type,X-Request-ID` |

## Frontend build contract

| Variable | Production value / requirement |
| --- | --- |
| `VITE_API_BASE_URL` | `/api` when the frontend proxy routes to the API; otherwise the explicit HTTPS API URL |
| `VITE_API_PROXY_TARGET` | Internal API target used only by the build/runtime proxy; never a browser secret |
| `VITE_ERROR_REPORTING_ENABLED` | `true` after backend client-error ingestion is monitored |
| `VITE_APP_ENV` | `production` |
| `VITE_APP_RELEASE` | Same immutable release ID as `APP_RELEASE` |

## Deployment verification

Before promotion, run the production-settings test and boot a production-like
API with secret-store values injected. Validate `/health/live`, `/health/ready`,
the HTTPS frontend origin, CORS preflight from `https://app.flipradar.com`, and
the release tag in API logs and error reports. Never print environment values in
CI logs.

## Release container certification

`docker-compose.release.yml` is the production-equivalent local and CI stack.
It builds the backend's `production` target and the frontend's Nginx/static
`production` target without source-code bind mounts. It uses local Postgres and
Redis only for certification; deployment environments must provide separate
managed dependencies and secret-store values.

Run the complete release check with:

```bash
make certify-release-containers
```

The check builds immutable local images, runs migrations as a separate release
step, then verifies API liveness/readiness behavior, SPA fallback routing,
fingerprinted static assets, the Nginx `/api` proxy, and API SIGTERM shutdown.
It creates an isolated temporary Compose project and removes only that project's
volumes when complete.

For an operator-managed staging deployment, copy
`deploy/staging.env.example` to the ignored `deploy/staging.env`, inject the
real staging secrets, and use the matching immutable image references. Then run:

1. `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml --profile migrations run --rm migrations`
2. `docker compose --env-file deploy/staging.env -f docker-compose.staging.yml up -d backend frontend`
3. Run the deployment smoke checks through the public frontend URL.

`docker-compose.staging.yml` has no build instructions, source mounts, database,
or Redis service: it deploys only the exact pre-built images against external
staging dependencies. Its environment template includes the release identifier,
Sentry/error-rate settings, and the explicit CORS contract needed for staging.
Promotion must use the exact tag already certified in staging; do not rebuild an
image for production.
