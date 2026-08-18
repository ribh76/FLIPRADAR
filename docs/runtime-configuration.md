# Runtime Configuration

FlipRadar runtime configuration is centralized in `flipradar.core.settings.Settings`.

## Environments

`APP_ENV` must be one of:

- `development`
- `test`
- `staging`
- `production`

Safe defaults are intended only for `development` and `test`. In `production`,
startup rejects debug mode, placeholder secrets, localhost endpoints, insecure
database SSL settings, and wildcard, HTTP, or localhost CORS origins.

## Settings Groups

- Application: `settings.application`
- Database: `settings.database`
- Authentication: `settings.auth`
- Email: `settings.email`
- Marketplace APIs: `settings.marketplace`
- LLM APIs: `settings.llm`
- Logging: `settings.logging`
- CORS: `settings.cors`

Environment variables are flat for deployment compatibility and grouped in Python for runtime use.

## Required Production Values

Production must provide:

- `APP_ENV=production`
- `APP_DEBUG=false`
- A strong `JWT_SECRET_KEY`
- A non-local PostgreSQL `DATABASE_URL` (or non-local database host) with a real `DATABASE_PASSWORD`
- `DATABASE_SSL_MODE=require`, `verify-ca`, or `verify-full`
- HTTPS `FRONTEND_URL` and explicit HTTPS `CORS_ALLOWED_ORIGINS`
- A non-local `REDIS_URL` (and non-local Celery URLs when explicitly configured)

Optional integrations such as email, eBay, BrickLink, and LLM providers may be
disabled in production. If one is enabled, all of its credentials must be
present and must not be development placeholders; otherwise startup fails.

## Anthropic

FlipRadar's LLM integration currently supports Anthropic only. Set
`LLM_ENABLED=true` and provide `ANTHROPIC_API_KEY` through the backend runtime
environment (or the ignored `backend/.env` file for local development). Never
place the API key in source files, frontend configuration, or Docker Compose.

LLM narratives use bounded retries, a per-user and global rolling-window rate
limit, and deterministic fallback. Configure `LLM_MAX_RETRIES`,
`LLM_USER_RATE_LIMIT`, `LLM_GLOBAL_RATE_LIMIT`, and
`LLM_RATE_LIMIT_WINDOW_SECONDS` for the deployment. Usage logs contain the
model, prompt version, token counts, latency, retry count, and estimated cost;
they never contain prompts, provider payloads, or credentials. The token-cost
rates are configuration values so they can be kept current with the selected
model's published pricing.

## Tests

Pytest configures `APP_ENV=test`, a test JWT secret, SQLite `DATABASE_URL`, and test CORS origins before app creation. Tests override the database dependency with in-memory SQLite sessions, so they do not require production credentials or live provider APIs.

## App Factory

The FastAPI app is built by `flipradar.main:create_app`. Uvicorn should use factory mode:

```bash
python3 -m uvicorn flipradar.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```
