# Part catalog limitations

The current catalog synchronization is intentionally a foundation, not a claim
of complete LEGO inventory coverage.

- Only the deterministic BrickLink-compatible mock provider is implemented.
  Production coverage, provider authentication, rate limiting, retries, and
  provider-specific change feeds still need a live adapter.
- Canonical identity is derived from one provider-stable identifier. Cross-provider
  equivalence is retained as extra provider IDs but is not independently proven;
  conflicting source records need review before they are merged automatically.
- A local search does not refresh stale records. Use `POST /parts/sync` to request
  a refresh; automated freshness scheduling and expiry policy remain future work.
- Name and alias matching is case-insensitive substring matching. It is not a
  typo-tolerant, language-aware, or ranked full-text search.
- Images, aliases, mold variants, and year ranges are provider assertions. They
  are merged without deleting prior observations, so obsolete provider values can
  remain until a curation/reconciliation workflow is added.
- `quality_flags` identify missing optional metadata and absent source timestamps.
  They do not certify correctness, authenticity, availability, price, or physical
  interchangeability of parts and variants.
