# Confidence, Freshness, And Data Limits

FlipRadar surfaces confidence and freshness so an estimate can be read with its
evidence, rather than as a precise promise.

## Confidence

Confidence reflects the quality and fit of available market evidence. It is higher
when the app has recent, condition-appropriate pricing with enough relevant
listings and matching evidence. It is lower when samples are small, a listing is
ambiguous, a market source is sparse, or the holding's condition does not closely
match the available data.

Confidence describes the evidence behind an estimate; it is not a probability
that a recommendation will be profitable. A high-confidence estimate can still
change if the market changes, and a low-confidence estimate can still prove
accurate.

## Freshness

Freshness is the retrieval time of the price snapshot or watchlist observation.
Recent data is generally more useful for a time-sensitive buying decision. A
stale or missing snapshot is called out in portfolio views, and a refresh can
collect newer data when a configured marketplace provider is available.

Demo snapshots intentionally use fixed timestamps so the demo is repeatable.
They demonstrate the UI and analytics paths; they are not live pricing.

## Data Limits

- Marketplace data can be incomplete, delayed, unavailable, or filtered by a
  provider.
- Asking prices are not completed sale prices, and completed sales can contain
  bundles, missing pieces, or condition differences.
- Set matching is based on supplied listing text and metadata. Review the source
  listing before acting.
- Values do not include every cost of buying or selling, such as taxes, fees,
  shipping, insurance, storage, and restoration.
- Portfolio results are informative only. They are not investment, tax, or
  financial advice.

See [Pricing Validation Methodology](pricing-validation-methodology.md) for
validation details and [AI Limitations](ai-limitations.md) for the optional
narrative layer's constraints.
