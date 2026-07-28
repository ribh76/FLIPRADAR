# Pricing validation methodology

FlipRadar stores one price-snapshot row per set, marketplace, condition, currency, metric, and retrieval time. The supported metrics are `low`, `median`, `average`, `high`, and `fair_market_value`.

## Source and evidence

Every snapshot exposes `source_payload`. It records the contributing marketplace listings, converted amounts, original amounts and currencies, and any listings excluded as outliers. `sample_size` is the number of comparable listings that remained after validation.

The set-detail and snapshot APIs expose this source payload, sample size, and `retrieval_time`. Retrieval time is the freshness timestamp: consumers should compare it with the configured pricing freshness threshold (`PRICING_FRESHNESS_HOURS`, 24 hours by default).

## Eligibility

Only listings that match the requested set with confidence at or above the automated-pricing threshold are eligible for valuation. Listings with unknown condition are not placed into a condition bucket. Pricing is kept separate for `new`, `used_complete`, and `incomplete` items.

## Outlier validation

For each condition, comparable currency group, and refresh, the pipeline applies Tukey’s IQR rule when at least four prices are available:

1. Calculate the first and third quartiles using the inclusive quartile method.
2. Calculate `IQR = Q3 - Q1`.
3. Keep prices within `[Q1 - 1.5 × IQR, Q3 + 1.5 × IQR]`.
4. Exclude prices outside the fences from all metrics.

When fewer than four comparable prices are available, IQR filtering is not applied; the snapshot retains the low-volume sample and its smaller `sample_size`. The applied method, fences, and excluded count are recorded in `source_payload.outlier_handling`.

## Metrics and estimation

`low`, `high`, `median`, and `average` summarize the validated sample. `fair_market_value` currently uses the validated median, which is less sensitive to skew than the average. The estimation engine uses fair-market value, then median, then average as fallbacks, while using low and high for the market range.

## Valuation engine

Valuations are available only for the supported condition buckets: `new`,
`used_complete`, and `incomplete`. The engine selects snapshots for the requested
set and condition, rejects stale snapshots (24 hours by default), and rejects
snapshot evidence below the automated-pricing confidence threshold. Imported
legacy snapshots without freshness or listing-confidence metadata remain usable
so historical valuations can still be viewed.

The estimate treats each marketplace/retrieval as one observation. It uses
Tukey's 1.5-IQR rule across marketplace observations when four or more are
available, then calculates a weighted expected value. Weights combine marketplace
reliability, a capped square-root sample-size factor, and listing evidence; sold
listings receive a 1.5x weight relative to active listings. The result exposes
`low_value`, `expected_value`, `high_value`, a 0–100 `confidence_score`, a
confidence band, methodology version, and every included or excluded input.

## Valuation guardrails and overrides

When no eligible snapshot remains after condition, freshness, confidence, or
outlier checks, the estimator returns `valuation_status: insufficient_data` and
an `insufficient_data` error rather than inventing a price. Analysis requests
return HTTP 422 with this message until usable evidence is refreshed.

A user may supply a documented manual override with an expected value, optional
low/high range, and a reason. The range must satisfy `low ≤ expected ≤ high`.
Manual overrides are marked as `manual_override` in the estimate and saved
analysis summary, so they are never presented as marketplace-derived prices.

## Currency

Values are converted to the configured pricing currency using Frankfurter’s daily exchange rate. Original listing amounts and currencies remain in the source payload and marketplace-listing records so the valuation is auditable.
