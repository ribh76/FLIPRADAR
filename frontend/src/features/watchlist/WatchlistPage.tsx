import { RefreshCw, Search, Trash2 } from "lucide-react";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  StatusBadge,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient, getApiError } from "../../services/apiClient";
import type {
  WatchlistHistoryPoint,
  WatchlistItem,
  WatchlistReplacement,
} from "../../types";
import { currency, percent } from "../../utils/format";

function checkedAt(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not checked yet";
}

function downloadCsv(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function WatchlistPage() {
  const navigate = useNavigate();
  const query = useServerQuery<WatchlistItem[]>(
    ["watchlist"],
    useCallback(() => apiClient.watchlist.list(), []),
  );
  const [message, setMessage] = useState("");
  const [busyId, setBusyId] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [history, setHistory] = useState<
    Record<string, WatchlistHistoryPoint[]>
  >({});
  const [replacements, setReplacements] = useState<
    Record<string, WatchlistReplacement[]>
  >({});

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
  async function loadHistory(item: WatchlistItem) {
    try {
      const points = await apiClient.watchlist.history(item.id);
      setHistory((current) => ({ ...current, [item.id]: points }));
    } catch (error) {
      setMessage(getApiError(error));
    }
  }
  async function findReplacements(item: WatchlistItem) {
    try {
      const results = await apiClient.watchlist.replacements(item.id);
      setReplacements((current) => ({ ...current, [item.id]: results }));
    } catch (error) {
      setMessage(getApiError(error));
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
          <h2 className="text-2xl font-bold">Saved sets and listings</h2>
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
        <button
          className="secondary-button"
          onClick={() => void apiClient.watchlist.export()
            .then((blob) => downloadCsv(blob, "flipradar-watchlist.csv"))
            .catch((error) => setMessage(getApiError(error)))}
          type="button"
        >
          Export CSV
        </button>
      </div>
      {message ? (
        <p className="text-sm text-[var(--color-text-muted)]" role="status">
          {message}
        </p>
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
            <StatusBadge value={item.recommendation} />
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
            {item.entry_type === "set" ? (
              <button
                className="primary-button"
                onClick={() =>
                  navigate(
                    `/portfolio?set_number=${encodeURIComponent(item.set_number)}`,
                  )
                }
                type="button"
              >
                Add to portfolio
              </button>
            ) : null}
            <button
              className="secondary-button"
              onClick={() =>
                navigate(`/sets/${encodeURIComponent(item.set_number)}`)
              }
              type="button"
            >
              View set
            </button>
            {item.last_known_listing_status === "ended" ||
            item.last_known_listing_status === "removed" ? (
              <p className="self-center text-sm text-[var(--color-loss)]">
                This listing is no longer available. Its last known price is
                retained.
              </p>
            ) : null}
            <button
              className="secondary-button"
              onClick={() => void loadHistory(item)}
              type="button"
            >
              Price history
            </button>
            {item.last_known_listing_status === "ended" ||
            item.last_known_listing_status === "removed" ? (
              <button
                className="secondary-button"
                onClick={() => void findReplacements(item)}
                type="button"
              >
                <Search size={16} />
                Find replacements
              </button>
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
          {history[item.id] ? (
            <PriceHistoryChart points={history[item.id]} />
          ) : null}
          {replacements[item.id] ? (
            <div className="mt-4 space-y-2">
              <p className="metric-label">Replacement listings</p>
              {replacements[item.id].length ? (
                replacements[item.id].map((replacement) => (
                  <a
                    className="block rounded border border-[var(--color-border-soft)] p-3 text-sm hover:border-[var(--color-accent)]"
                    href={replacement.url}
                    key={replacement.listing_id}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {replacement.title} ·{" "}
                    {currency(replacement.total_price, replacement.currency)} ·{" "}
                    <strong>{replacement.recommendation}</strong>
                  </a>
                ))
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">
                  No active replacements found.
                </p>
              )}
            </div>
          ) : null}
        </article>
      ))}
    </section>
  );
}

function PriceHistoryChart({ points }: { points: WatchlistHistoryPoint[] }) {
  const values = points
    .map((point) => Number(point.listing_price ?? point.fair_value))
    .filter(Number.isFinite);
  if (!values.length)
    return (
      <p className="mt-4 text-sm text-[var(--color-text-muted)]">
        No price observations yet.
      </p>
    );
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || 1;
  const chartPoints = points
    .map(
      (point, index) =>
        `${index * (100 / Math.max(points.length - 1, 1))},${100 - ((Number(point.listing_price ?? point.fair_value) - low) / range) * 100}`,
    )
    .join(" ");
  return (
    <div className="mt-4">
      <p className="metric-label">Price history</p>
      <svg
        aria-label="Price history chart"
        className="mt-2 h-28 w-full overflow-visible"
        preserveAspectRatio="none"
        viewBox="0 0 100 100"
      >
        <polyline
          fill="none"
          points={chartPoints}
          stroke="var(--color-accent)"
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <p className="text-xs text-[var(--color-text-muted)]">
        {points.length} observations. Prices range from {currency(low)} to {currency(high)}.
      </p>
    </div>
  );
}
