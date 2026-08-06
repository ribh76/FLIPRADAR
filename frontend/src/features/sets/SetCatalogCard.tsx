import { ExternalLink, PackageOpen } from "lucide-react";
import { useState } from "react";
import { Card, MetricCard } from "../../components/ui";
import { apiClient, getApiError } from "../../services/apiClient";
import type { LegoSet } from "../../types";
import { currency, numberValue } from "../../utils/format";

type SetCatalogCardProps = {
  set: LegoSet;
  onViewDetail?: (setNumber: string) => void;
};

function updatedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Update time unavailable"
    : `Updated ${date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })}`;
}

export function SetCatalogCard({ set, onViewDetail }: SetCatalogCardProps) {
  const [watchlistMessage, setWatchlistMessage] = useState("");
  const imageUrl = set.image_urls?.[0];
  const retirementStatus = set.retirement_year
    ? `Retired ${set.retirement_year}`
    : "Retirement not reported";

  return (
    <Card className="overflow-hidden">
      <div className="grid gap-5 md:grid-cols-[180px_1fr]">
        <div className="flex min-h-44 items-center justify-center overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border-soft)] bg-[var(--color-surface-muted)]">
          {imageUrl ? (
            <img
              alt={`${set.name} LEGO set`}
              className="h-full w-full object-cover"
              src={imageUrl}
            />
          ) : (
            <PackageOpen
              aria-label="Set image unavailable"
              className="text-[var(--color-text-muted)]"
              size={42}
            />
          )}
        </div>

        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="metric-label">{set.set_number}</p>
              <h2 className="mt-1 text-2xl font-bold text-[var(--color-text)]">
                {set.name}
              </h2>
              <p className="mt-2 text-sm font-semibold text-[var(--color-text-muted)]">
                {updatedAt(set.updated_at)}
              </p>
            </div>
            {onViewDetail ? (
              <button
                className="secondary-button"
                onClick={() => onViewDetail(set.set_number)}
                type="button"
              >
                View detail
              </button>
            ) : null}
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Theme" value={set.theme ?? "--"} />
            <MetricCard
              label="Release year"
              value={set.release_year?.toString() ?? "--"}
            />
            <MetricCard label="Pieces" value={numberValue(set.piece_count)} />
            <MetricCard
              label="MSRP"
              value={currency(set.msrp, set.original_currency ?? "USD")}
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm font-semibold text-[var(--color-text-muted)]">
            <span>{retirementStatus}</span>
            {set.source_name ? (
              set.source_url ? (
                <a
                  className="inline-flex items-center gap-1 text-[var(--color-accent)] hover:underline"
                  href={set.source_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  Source: {set.source_name} <ExternalLink size={14} />
                </a>
              ) : (
                <span>Source: {set.source_name}</span>
              )
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap gap-3 border-t border-[var(--color-border-soft)] pt-5">
            <button className="secondary-button" disabled type="button">
              Add to portfolio
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                void apiClient.watchlist
                  .addSet(set.set_number)
                  .then(() => setWatchlistMessage("Saved to watchlist."))
                  .catch((error: unknown) =>
                    setWatchlistMessage(getApiError(error)),
                  )
              }
              type="button"
            >
              Add to watchlist
            </button>
          </div>
          {watchlistMessage ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              {watchlistMessage}
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
