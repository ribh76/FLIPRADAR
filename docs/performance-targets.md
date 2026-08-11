# Performance Targets

These targets apply to the local Docker stack using seeded demo data. They are
guardrails for regressions, not production SLOs; production targets should be
set from real traffic telemetry.

| Path | Target | Scope |
| --- | --- | --- |
| Frontend shell | TTFB under 250 ms | Local cold request |
| `GET /health` | p95 under 250 ms | 25 requests, concurrency 5 |
| Portfolio dashboard | p95 under 500 ms | Authenticated, cached valuation read |
| Catalog type-ahead | p95 under 300 ms | Local catalog results, 6 rows |
| Marketplace refresh | Each provider attempt times out at 10 s | Partial results remain usable |

## Regression checks

`scripts/benchmark_local_performance.sh` checks the health p95 target and
returns a non-zero status on a breach. Override the target only when recording
an intentional environment-specific baseline:

```bash
MAX_HEALTH_P95_SECONDS=0.4 bash scripts/benchmark_local_performance.sh
```

Backend unit tests verify cache coalescing and partial provider success. The
frontend typecheck/build verifies lazy route chunks, while component tests cover
the search and catalog surfaces. Run the normal quality gate before merging:

```bash
make quality
```
