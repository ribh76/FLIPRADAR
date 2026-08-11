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
