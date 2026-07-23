# Runtime Configuration

FlipRadar runtime configuration is centralized in `flipradar.core.settings.Settings`.

## Environments

`APP_ENV` must be one of:

- `development`
- `test`
- `staging`
- `production`

Safe defaults are intended only for `development` and `test`. `production` validates that debug mode is disabled, JWT and database secrets are not local placeholders, SSL is required for the database, and CORS origins are explicit.

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
- A real `DATABASE_PASSWORD` or `DATABASE_URL`
- `DATABASE_SSL_MODE=require`, `verify-ca`, or `verify-full`
- Explicit `CORS_ALLOWED_ORIGINS`

Optional integrations such as email, eBay, BrickLink, and LLM providers remain disabled unless both enabled and configured. Startup logs report disabled optional integrations clearly.

## Tests

Pytest configures `APP_ENV=test`, a test JWT secret, SQLite `DATABASE_URL`, and test CORS origins before app creation. Tests override the database dependency with in-memory SQLite sessions, so they do not require production credentials or live provider APIs.

## App Factory

The FastAPI app is built by `flipradar.main:create_app`. Uvicorn should use factory mode:

```bash
python3 -m uvicorn flipradar.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```
