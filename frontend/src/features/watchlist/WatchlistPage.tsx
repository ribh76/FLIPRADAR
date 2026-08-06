import { RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useState } from "react";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  StatusBadge,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient, getApiError } from "../../services/apiClient";
import type { WatchlistItem } from "../../types";
import { currency, percent } from "../../utils/format";

function checkedAt(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not checked yet";
}

export function WatchlistPage() {
  const query = useServerQuery<WatchlistItem[]>(
    ["watchlist"],
    useCallback(() => apiClient.watchlist.list(), []),
  );
  const [message, setMessage] = useState("");
  const [busyId, setBusyId] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    setMessage("");
    try {
      query.setData(await apiClient.watchlist.refresh());
      setMessage("Watchlist refreshed.");
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setRefreshing(false);
    }
  }
  async function remove(item: WatchlistItem) {
    setBusyId(item.id);
    setMessage("");
    try {
      await apiClient.watchlist.remove(item.id);
      query.setData(
        (query.data ?? []).filter((current) => current.id !== item.id),
      );
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setBusyId("");
    }
  }
  async function move(item: WatchlistItem) {
    setBusyId(item.id);
    setMessage("");
    try {
      await apiClient.watchlist.moveToPortfolio(item.id);
      query.setData(
        (query.data ?? []).filter((current) => current.id !== item.id),
      );
      setMessage("Moved to your portfolio.");
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setBusyId("");
    }
  }
  if (query.isLoading) return <LoadingState title="Loading watchlist..." />;
  if (query.error)
    return (
      <ErrorState
        message={query.error}
        onRetry={() => void query.refetch()}
        title="Watchlist unavailable"
      />
    );
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="metric-label">Manual watchlist</p>
          <h1 className="text-2xl font-bold">Saved sets and listings</h1>
        </div>
        <button
          className="secondary-button"
          disabled={refreshing}
          onClick={() => void refresh()}
          type="button"
        >
          <RefreshCw className={refreshing ? "animate-spin" : ""} size={16} />
          {refreshing ? "Refreshing..." : "Refresh all"}
        </button>
      </div>
      {message ? (
        <p className="text-sm text-[var(--color-text-muted)]">{message}</p>
      ) : null}
      {query.data?.length === 0 ? (
        <EmptyState
          message="Save a set or listing from catalog, deals, or the listing evaluator."
          title="Your watchlist is empty"
        />
      ) : null}
      {query.data?.map((item) => (
        <article className="page-card" key={item.id}>
          <div className="flex flex-wrap justify-between gap-3">
            <div>
              <p className="metric-label">
                {item.entry_type === "listing" ? "Listing" : "Set"} ·{" "}
                {item.set_number}
              </p>
              <h2 className="mt-1 text-lg font-bold">
                {item.entry_type === "listing"
                  ? "Marketplace listing"
                  : "Set market watch"}
              </h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                Last checked: {checkedAt(item.last_checked_at)}
              </p>
            </div>
            {item.last_known_listing_status ? (
              <StatusBadge
                value={item.last_known_listing_status.toUpperCase()}
              />
            ) : null}
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Current price"
              value={currency(item.current_price)}
            />
            <MetricCard label="Target" value={currency(item.target_price)} />
            <MetricCard label="Valuation" value={currency(item.valuation)} />
            <MetricCard
              label="Discount"
              value={percent(item.discount_percent)}
            />
            <MetricCard
              label="Last checked"
              value={checkedAt(item.last_checked_at)}
            />
          </div>
          {item.notes ? (
            <p className="mt-4 text-sm text-[var(--color-text-muted)]">
              {item.notes}
            </p>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-3 border-t border-[var(--color-border-soft)] pt-4">
            {item.entry_type === "listing" &&
            item.last_known_listing_status === "active" ? (
              <button
                className="primary-button"
                disabled={busyId === item.id}
                onClick={() => void move(item)}
                type="button"
              >
                Move to portfolio
              </button>
            ) : null}
            {item.last_known_listing_status === "ended" ||
            item.last_known_listing_status === "removed" ? (
              <p className="self-center text-sm text-[var(--color-loss)]">
                This listing is no longer available. Its last known price is
                retained.
              </p>
            ) : null}
            <button
              aria-label={`Remove ${item.set_number} from watchlist`}
              className="secondary-button"
              disabled={busyId === item.id}
              onClick={() => void remove(item)}
              type="button"
            >
              <Trash2 size={16} />
              Remove
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
