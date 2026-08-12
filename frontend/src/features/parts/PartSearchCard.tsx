import { PackageOpen, Tag } from "lucide-react";
import { Badge, Card, MetricCard } from "../../components/ui";
import type { PartCatalogSearchResult } from "../../types";
import { currency } from "../../utils/format";

export function PartSearchCard({ part }: { part: PartCatalogSearchResult }) {
  const imageUrl = part.image_urls[0];
  const years = [part.first_known_year, part.last_known_year]
    .filter((year): year is number => year !== null)
    .join("–");

  return (
    <Card className="overflow-hidden">
      <div className="grid gap-5 md:grid-cols-[144px_1fr]">
        <div className="flex min-h-36 items-center justify-center overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border-soft)] bg-[var(--color-surface-muted)]">
          {imageUrl ? (
            <img
              alt={part.name}
              className="h-full w-full object-contain p-3"
              decoding="async"
              height="144"
              loading="lazy"
              src={imageUrl}
              width="144"
            />
          ) : (
            <PackageOpen className="text-[var(--color-text-muted)]" size={38} />
          )}
        </div>
        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="metric-label">{part.canonical_identifier}</p>
              <h2 className="mt-1 text-xl font-bold text-[var(--color-text)]">
                {part.name}
              </h2>
              <p className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-[var(--color-text-muted)]">
                <Tag size={15} /> {part.match_explanation}
              </p>
            </div>
            <Badge
              tone={part.match_confidence === "exact" ? "success" : "info"}
            >
              {part.match_confidence} match
            </Badge>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <MetricCard label="Category" value={part.category?.name ?? "--"} />
            <MetricCard label="Known years" value={years || "--"} />
            <MetricCard
              label="Market price"
              value={
                part.market_price === null
                  ? "Not available"
                  : currency(
                      part.market_price,
                      part.market_price_currency ?? "USD",
                    )
              }
            />
          </div>

          <div className="mt-4 space-y-3 text-sm">
            <div>
              <p className="field-label">Available colors</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {part.available_colors.length ? (
                  part.available_colors.map((color) => (
                    <span
                      className="rounded-full border border-[var(--color-border-soft)] bg-[var(--color-surface-muted)] px-3 py-1 font-semibold text-[var(--color-text)]"
                      key={color.id}
                    >
                      {color.name}
                    </span>
                  ))
                ) : (
                  <span className="text-[var(--color-text-muted)]">
                    Not reported
                  </span>
                )}
              </div>
            </div>
            <div>
              <p className="field-label">Mold variants</p>
              {part.mold_variants.length ? (
                <ul className="mt-2 space-y-1 text-[var(--color-text-muted)]">
                  {part.mold_variants.map((variant, index) => (
                    <li key={`${part.id}-${index}`}>
                      {typeof variant === "string"
                        ? variant
                        : [variant.identifier, variant.description]
                            .filter(Boolean)
                            .join(" — ")}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-[var(--color-text-muted)]">
                  Not reported
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
