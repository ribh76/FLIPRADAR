# Advanced pricing analytics

This feature keeps raw metric observations for two years by default
(`PRICING_RETENTION_DAYS=730`). When retention runs, older raw observations are
first compacted into both weekly and monthly rollups and are only then deleted.
Rollups are keyed by set, marketplace, condition, currency, metric, period and
calendar-period start. Re-running compaction replaces the same rollup, making
the operation safe to retry.

The analytics endpoint is `GET /snapshots/{set_number}/analytics`. It defaults
to comparable `new`, `fair_market_value`, USD observations. The condition,
metric type, and currency can be supplied as query parameters. It is
descriptive analytics, not a price forecast: the retained and compacted series
is the historical dataset intended for future forecast experiments.

## Series construction

For a calendar day, observations from all matching marketplaces are averaged.
Recent raw observations provide day-level points. Older monthly rollups provide
one point at the start of each month, using that rollup's average value. Weekly
rollups are retained for weekly charting and export; the monthly series is used
for long-range calculations so the same observation is never counted twice.

## Calculations

| Metric | Calculation |
| --- | --- |
| Rolling averages | Arithmetic mean of normalized series points dated in the trailing 7, 30, or 90 calendar days, inclusive. |
| Volatility | Population standard deviation of consecutive percentage changes, returned as a percentage. At least two returns (three points) are required. It is not annualized. |
| Marketplace spread | Latest matching observation per marketplace; high minus low and that amount divided by the low. Different currencies are never mixed. |
| Liquidity proxies | Latest marketplace count, sum of their reported sample sizes, and normalized-series observations in the last 30 days. `proxy_score` is capped at 100: `25 × marketplace_count + min(25, sample_size) + min(25, 5 × observations_30d)`. It is a comparability signal, not a measure of actual sales volume. |
| Drawdown | `(latest normalized value - recorded series high) / recorded series high × 100`. Negative values indicate the latest price is below the recorded high. |

Missing metrics are returned as `null` rather than inferred. In particular,
volatility is null for fewer than three usable points, and a percentage spread
is null when the lowest marketplace value is zero.

## Predictive experimentation guardrails

Any future forecast must record its training cutoff, selected condition,
metric, currency, rollup granularity, and the number of source observations.
It must never train across currencies or conditions, treat the liquidity proxy
as sales volume, or present descriptive metrics as a forecast confidence band.
