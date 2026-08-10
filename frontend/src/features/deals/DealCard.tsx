import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, MetricCard } from "../../components/ui";
import { apiClient, getApiError } from "../../services/apiClient";
import type { Deal } from "../../types";
import { currency, percent } from "../../utils/format";

export function DealCard({ deal }: { deal: Deal }) {
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="metric-label">{deal.set_number}</p>
          <h2 className="mt-1 text-xl font-bold text-[var(--color-text)]">
            {deal.set_name}
          </h2>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            {deal.title}
          </p>
        </div>
        <Badge tone={deal.score >= 70 ? "success" : "warning"}>
          {deal.deal_band} deal
        </Badge>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="All-in price"
          value={currency(deal.total_cost, deal.currency)}
        />
        <MetricCard
          label="Estimated value"
          value={currency(deal.value, deal.currency)}
        />
        <MetricCard label="Discount" value={percent(deal.discount)} />
        <MetricCard label="Deal score" value={`${deal.score}/100`} />
        <MetricCard label="Confidence" value={`${deal.confidence}/100`} />
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--color-border-soft)] pt-4">
        <div className="text-sm text-[var(--color-text-muted)]">
          <span className="font-bold text-[var(--color-text)]">
            {deal.marketplace.display_name}
          </span>
          {deal.marketplace.seller_name
            ? ` · ${deal.marketplace.seller_name}`
            : ""}
          {deal.marketplace.seller_rating !== null
            ? ` (${deal.marketplace.seller_rating}% seller rating)`
            : ""}
          {` · ${deal.is_sealed ? "sealed" : deal.condition}`}
        </div>
        <a
          className="primary-button"
          href={deal.url}
          rel="noreferrer"
          target="_blank"
        >
          View listing <ExternalLink aria-hidden="true" size={16} />
        </a>
        <button
          className="secondary-button"
          onClick={() =>
            void apiClient.watchlist
              .addListing(deal.listing_id)
              .then(() => setMessage("Saved to watchlist."))
              .catch((error: unknown) => setMessage(getApiError(error)))
          }
          type="button"
        >
          Save to watchlist
        </button>
        <button
          className="secondary-button"
          onClick={() =>
            navigate(
              `/listing-evaluator?set_number=${encodeURIComponent(deal.set_number)}&url=${encodeURIComponent(deal.url)}`,
            )
          }
          type="button"
        >
          Evaluate listing
        </button>
        <button
          className="secondary-button"
          onClick={() =>
            navigate(
              `/portfolio?set_number=${encodeURIComponent(deal.set_number)}`,
            )
          }
          type="button"
        >
          Add to portfolio
        </button>
      </div>
      {message ? (
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{message}</p>
      ) : null}
      <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
        {deal.explanation}
      </p>
    </Card>
  );
}
