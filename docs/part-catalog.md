# Part catalog synchronization

The part catalog is provider-neutral at the storage boundary. Each category,
color, part, and element stores all supplied provider identifiers in
`provider_identifiers`; the provider adapter is responsible for putting the
provider's record into the normalized shape before it reaches the repository.

## Identity, duplicates, and variants

`canonical_identifier` is the unique identity for each catalog entity. The
normalizer derives it from the stable catalog identifier, such as `part:3001`
or `element:300121`. A synchronization therefore updates an existing record
rather than creating a duplicate when a provider returns it again.

Parts are not duplicated for each color. An `Element` records a sellable
part/color combination, so a part's available colors are derived from its
elements. This preserves separate element identifiers while keeping one part
record. Refreshes merge provider identifiers, aliases, image URLs, and mold
variants by value; they never discard a previously known variant merely because
it is absent from a later provider response.

## Freshness and sources

Every record records `source_name`, `source_url`, optional
`source_updated_at`, and the local `fetched_at` time. A sync refreshes those
timestamps and mutable provider fields. The search endpoint reads local data
first and only calls the provider for a local miss; `POST /parts/sync` forces a
provider refresh for a query.

## Search indexes

Unique canonical-identifier indexes make synchronization safe. Name indexes on
all catalog entities and part/category and element/part/color composite indexes
support lookup and relation traversal. The current provider adapter is a
deterministic BrickLink-compatible mock; replacing it with a live adapter does
not change the normalized persistence contract.
