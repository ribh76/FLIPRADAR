import { RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageState,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient, getApiError } from "../../services/apiClient";
import type { DealsResponse } from "../../types";
import { DealCard } from "./DealCard";

export function DealsPage() {
  const loadDeals = useCallback(() => apiClient.deals.list(), []);
  const dealsQuery = useServerQuery<DealsResponse>(["deals", 25, 0], loadDeals);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  async function refreshDeals() {
    setIsRefreshing(true);
    setRefreshError("");
    try {
      const refreshed = await apiClient.deals.list({ refresh: true });
      dealsQuery.setData(refreshed);
    } catch (error) {
      setRefreshError(getApiError(error));
    } finally {
      setIsRefreshing(false);
    }
  }

  const refresh = dealsQuery.data?.refresh;
  const hasCards = Boolean(dealsQuery.data?.data.length);

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-muted)]">
            Bounded catalog discovery
          </p>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Active, matched listings ranked by all-in discount and confidence.
          </p>
        </div>
        <button
          className="primary-button"
          disabled={isRefreshing}
          onClick={() => void refreshDeals()}
          type="button"
        >
          <RefreshCw className={isRefreshing ? "animate-spin" : ""} size={16} />
          {isRefreshing ? "Refreshing..." : "Refresh deals"}
        </button>
      </div>

      {refresh?.throttled ? (
        <PageState title="Refresh is cooling down" tone="warning">
          Try again in {refresh.retry_after_seconds ?? 60} seconds. Showing the
          most recent saved results.
        </PageState>
      ) : null}
      {refresh?.provider_errors.length ? (
        <PageState title="Partial marketplace results" tone="warning">
          {refresh.provider_errors.join(" ")} Existing deal cards remain
          available while the next refresh retries the provider.
        </PageState>
      ) : null}
      {refreshError ? (
        <ErrorState
          message={
            hasCards
              ? `${refreshError} Showing previous deal results.`
              : refreshError
          }
          onRetry={() => void refreshDeals()}
          title="Refresh unavailable"
        />
      ) : null}
      {dealsQuery.isLoading ? (
        <LoadingState title="Finding active deals..." />
      ) : null}
      {dealsQuery.error && !hasCards ? (
        <ErrorState
          message={dealsQuery.error}
          onRetry={() => void dealsQuery.refetch()}
          title="Deal finder unavailable"
        />
      ) : null}
      {!dealsQuery.isLoading && !dealsQuery.error && !hasCards ? (
        <EmptyState
          message="No eligible, recently seen listings have a matching fair-value estimate yet."
          title="No deals right now"
        />
      ) : null}
      {dealsQuery.data?.data.map((deal) => (
        <DealCard deal={deal} key={deal.listing_id} />
      ))}
    </section>
  );
}
