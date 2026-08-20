# Operations Guide

## Health checks

Use `GET /health/live` for a process liveness probe. It does not call any dependency.

Use `GET /health` or `GET /health/ready` for readiness. Both verify the database
and return HTTP `503` when it is unavailable. `GET /db-health` remains available
for compatibility and returns the same readiness envelope.

Successful responses have this shape:

```json
{
  "status": "healthy",
  "service": "FlipRadar API",
  "timestamp": "2026-08-11T19:00:00+00:00",
  "checks": {
    "application": { "status": "healthy" },
    "database": { "status": "healthy", "latency_ms": 4 }
  }
}
```

An unhealthy dependency is reported as `status: "unhealthy"`; failure details
are intentionally not returned to callers.

## Administrative and operational endpoint access

FlipRadar does not expose a platform-administrator or role-based management API
in production. Administrative actions are either performed by the authenticated
owner of a resource or are intentionally unavailable outside engineering
environments.

### Engineering and maintenance endpoints

The following operational endpoints are hidden from production OpenAPI and
respond with `404` in production. In development and staging they require HTTP
Basic credentials from `OPERATIONAL_ROUTE_USERNAME` and
`OPERATIONAL_ROUTE_PASSWORD`; the test environment bypasses this guard only for
automated fixture setup.

| Endpoint | Classification | Intended use |
| --- | --- | --- |
| `POST /sets` | Seed | Create local or test catalog records. |
| `POST /parts/sync` | Maintenance | Hydrate and persist provider part catalog data. |
| `POST /marketplace/update/{set_number}` | Refresh | Refresh raw marketplace data and create snapshots. |
| `POST /listings` | Internal | Insert a raw marketplace listing. |
| `GET /listings/{set_number}/latest` | Internal | Inspect the newest raw listing. |
| `POST /snapshots` | Internal | Insert a price snapshot. |
| `GET /snapshots/{set_number}` | Internal | Inspect stored snapshot history. |
| `GET /snapshots/{set_number}/analytics` | Internal | Run advanced snapshot analytics. |
| `GET /snapshots/{set_number}/latest` | Internal | Inspect the newest stored snapshot. |

Use a unique, secret password in any non-test deployment. Do not configure a
shared operational credential in production: these endpoints are not a
production support interface and remain unavailable there.

### Production account administration

The production endpoints that administer user data use an `Authorization:
Bearer <access-token>` header. They derive the user identity from the token and
scope all reads and writes to that identity; a caller cannot select another
user's account or resource by path parameter.

| Endpoint group | Authentication and authorization model |
| --- | --- |
| `/auth/me`, `/auth/logout`, `/auth/resend-verification` | JWT Bearer token for the current account. Logout also validates ownership of the supplied refresh session. |
| `/users/me`, `/users/me/mfa`, `/users/me/password`, `/users/me/deletion-request`, `/users/me/email-change/request`, `/users/me/sessions` | JWT Bearer token for the current account; sensitive changes additionally require their route-specific confirmation material, such as the current password. |
| `/portfolio/*`, `/watchlist/*`, `/inventory/*`, `/saved-searches/*`, `/notifications/*` | JWT Bearer token plus service-level ownership checks for the current user. |
| Auth recovery and verification endpoints | No access token by design; they require a short-lived, purpose-bound account or MFA token where applicable. Registration, login, and reset-request endpoints remain public entry points and must be rate-limited at the edge. |

`GET /health`, `/health/live`, `/health/ready`, and `/db-health` are public
deployment probes. They return only sanitized dependency status. `POST
/client-errors` accepts a sanitized browser error report and is not an
administrative endpoint; restrict it at the edge if your deployment does not
need browser error reporting.

The authorization test suite derives every JWT-protected production operation
from OpenAPI and verifies that an anonymous request receives `401`. Run it with:

```bash
./venv/bin/python -m pytest backend/tests/api/test_production_endpoint_testing.py
```

## Metrics and alerts

Metrics and alerts are JSON log events. Configure the existing log platform to
aggregate `metric.name` and alert on `metric.name == "alert.triggered"`.

- `database.health.check` and `database.health.latency` measure database health.
- `http.request` tracks successful and server-error HTTP outcomes.
- `llm.*` and `provider.cost` cover LLM usage, latency, failures, and estimated cost.
- `provider.*` tracks marketplace-provider outcomes and latency.
- `worker.job*` records background-job lifecycle and latency.

The API raises a critical `alert.triggered` event named `http_error_rate` when
the rolling server-error rate reaches the configured threshold. Defaults are
5% across at least 20 requests in five minutes. Configure these environment
variables per environment:

- `ERROR_RATE_ALERT_THRESHOLD_PERCENT`
- `ERROR_RATE_ALERT_MINIMUM_REQUESTS`
- `ERROR_RATE_ALERT_WINDOW_SECONDS`

Startup scripts emit a critical `deployment_failure` alert for unsuccessful
database wait or seed stages and a `migration_failure` alert when Alembic fails.
Deploy alert rules should page on either alert in production and create a ticket
in non-production.

## Error monitoring and privacy

Set `SENTRY_DSN` and `APP_RELEASE` in the deployment environment to enable
exception monitoring. Browser reporting additionally requires
`VITE_ERROR_REPORTING_ENABLED=true`.

Telemetry redacts password, token, secret, API-key, DSN, username, user, and
email fields; common credential strings, bearer tokens, and the local demo
account identifiers are also removed before logs or error events are emitted.
Do not place credentials in metric tags, exception messages, release names, or
deployment labels.

## Triage

1. Check `/health/live`; if it fails, restart or replace the API process.
2. Check `/health`; if the database check is unhealthy, inspect database health
   and connection limits before restarting application instances.
3. For `http_error_rate`, filter request logs by request ID and inspect the
   associated sanitized exception event.
4. For deployment or migration alerts, stop rollout, review the Alembic output,
   and apply a forward-only corrective migration. Do not roll back a production
   migration without a reviewed recovery plan.
5. For worker alerts, inspect the task name and retry/failure metrics before
   requeuing work.
