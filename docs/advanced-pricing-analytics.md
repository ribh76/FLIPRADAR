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

## Advanced comparisons and experimentation inputs

All calculations use one metric and currency at a time. The API also receives
the set catalog record, so no external lookups or unsupported assumptions are
introduced while reading a price series.

| Feature | Calculation and limits |
| --- | --- |
| Condition-adjusted comparison | Uses the validated snapshot-condition enum: `new=1.00`, `used_complete=0.78`, and `incomplete=0.45`. Each latest condition value is divided by its weight to show a new-equivalent comparison. This is an explicit heuristic—not an appraisal or a condition-grade substitute. |
| Theme benchmark index | Uses catalog release age as an experimental theme-age proxy: `1 + min(0.35, 0.015 × set age in years)`. The endpoint returns the theme, index (`weight × 100`), and age-weighted value. This does not claim that every set in a theme performs alike. |
| Retirement annotation | A retired set is annotated with its retirement year and years retired. Its rarity multiplier is `1 + min(0.30, 0.03 × years retired)`; the rarity-adjusted value applies that multiplier to the observed latest value. Non-retired sets have a multiplier of `1.00`. |
| MSRP comparison | Returns the observed latest value less original MSRP, both as a currency amount and percentage of MSRP. It returns null if MSRP is unavailable or its original currency conflicts with the requested analytics currency. |
| Inflation-adjusted view | Applies a flat annual worldwide rate of **4.1%** from release year: `MSRP × 1.041 ^ years`. It returns the adjusted MSRP plus observed-value difference in currency and percent. It is deliberately a temporary global assumption, not a regional CPI series. |
| Confidence band | A 1–5 evidence indicator: 1 red / low, 2 orange / low, 3 yellow / moderate, 4 blue / high, 5 green / high. It awards one point each beyond the base band for 3+ series points, 2+ marketplaces, sample size ≥10, and complete core catalog metadata without a quality flag. |
| Validation metrics | Exposes price-data presence, series-point count, marketplace count, sample size, catalog completeness, catalog quality flag, and whether the minimum experiment threshold is met (3 points, 2 marketplaces, and a latest value). |

## Chart-control contract

`chart_controls` supplies stock-chart style controls for clients: ranges
`1W`, `1M`, `3M`, `6M`, `YTD`, `1Y`, `5Y`, and `MAX`; daily/weekly/monthly
aggregation; line or area display; price, 7/30/90-day moving-average and
volume-proxy overlays; and marketplace, condition-adjusted, MSRP,
inflation-adjusted, and theme-benchmark comparison modes. The current response
defines the supported controls; clients should only enable a control when its
underlying metric is non-null.

Missing metrics are returned as `null` rather than inferred. In particular,
volatility is null for fewer than three usable points, and a percentage spread
is null when the lowest marketplace value is zero.

## Predictive experimentation guardrails

Any future forecast must record its training cutoff, selected condition,
metric, currency, rollup granularity, and the number of source observations.
It must never train across currencies or conditions, treat the liquidity proxy
as sales volume, treat condition/theme/retirement adjustments as ground truth,
or present descriptive metrics as a forecast confidence band.
