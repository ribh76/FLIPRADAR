import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Card,
  ErrorState,
  LoadingState,
  MetricCard,
  TextField,
} from "../../components/ui";
import { useServerMutation, useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import type { PortfolioItemUpdate } from "../../types";
import { currency, percent, signedCurrency } from "../../utils/format";

function freshnessLabel(timestamp: string | null): string {
  if (!timestamp) return "No market data yet";
  const hours = Math.max(
    0,
    Math.floor((Date.now() - new Date(timestamp).getTime()) / 3_600_000),
  );
  return hours < 1 ? "Updated within the hour" : `Updated ${hours}h ago`;
}

function ValueHistoryChart({
  points,
}: {
  points: { timestamp: string; value: string | number }[];
}) {
  const path = useMemo(() => {
    if (points.length < 2) return "";
    const values = points.map((point) => Number(point.value));
    const min = Math.min(...values);
    const span = Math.max(Math.max(...values) - min, 1);
    return points
      .map((point, index) => {
        const x = (index / (points.length - 1)) * 100;
        const y = 92 - ((Number(point.value) - min) / span) * 76;
        return `${index === 0 ? "M" : "L"} ${x} ${y}`;
      })
      .join(" ");
  }, [points]);

  if (points.length < 2) {
    return (
      <p className="text-sm text-[var(--color-text-muted)]">
        More marketplace snapshots are needed to draw a value trend.
      </p>
    );
  }
  return (
    <svg
      aria-label="Marketplace value history"
      className="h-52 w-full"
      role="img"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      <line
        x1="0"
        x2="100"
        y1="92"
        y2="92"
        stroke="var(--color-border-soft)"
        strokeWidth="1"
      />
      <path
        d={path}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="2.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function HoldingDetailPage() {
  const { itemId = "" } = useParams();
  const detailQuery = useServerQuery(
    ["portfolio-holding-detail", itemId],
    useCallback(() => apiClient.portfolio.detail(itemId), [itemId]),
    { enabled: Boolean(itemId) },
  );
  const [notes, setNotes] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const updateMutation = useServerMutation(
    (payload: PortfolioItemUpdate) =>
      apiClient.portfolio.updateItem(itemId, payload),
    { onSuccess: () => void detailQuery.refetch() },
  );
  const detail = detailQuery.data;
  const holding = detail?.holding;

  useEffect(() => {
    if (!holding) return;
    setNotes(holding.notes ?? "");
    setPurchaseDate(holding.purchase_date?.slice(0, 10) ?? "");
    setPurchasePrice(String(holding.purchase_price));
  }, [holding]);

  function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void updateMutation.mutate({
      notes: notes || null,
      purchase_price: Number(purchasePrice),
      purchase_date: purchaseDate
        ? new Date(`${purchaseDate}T00:00:00`).toISOString()
        : null,
    });
  }

  if (detailQuery.isLoading)
    return <LoadingState title="Loading holding analytics..." />;
  if (detailQuery.error || !detail || !holding) {
    return (
      <ErrorState
        message={detailQuery.error || "Holding not found."}
        onRetry={() => void detailQuery.refetch()}
        title="Holding detail unavailable"
      />
    );
  }

  const marketCondition =
    holding.condition === "sealed"
      ? "new"
      : holding.condition === "used"
        ? "used"
        : holding.condition;
  const history = detail.market_snapshots.filter(
    (snapshot) => snapshot.condition === marketCondition,
  );
  const riskTone =
    detail.concentration_risk.level === "high"
      ? "semantic-loss"
      : detail.concentration_risk.level === "moderate"
        ? "text-[var(--color-accent-warm)]"
        : "semantic-gain";

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            className="text-sm font-bold text-[var(--color-link)]"
            to="/portfolio"
          >
            ← Back to portfolio
          </Link>
          <h2 className="mt-2 text-2xl font-black text-[var(--color-text)]">
            {holding.set_name ?? holding.set_number}
          </h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Set {holding.set_number} · {holding.condition} condition ·{" "}
            {freshnessLabel(detail.market_freshness_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className="secondary-button" type="button">
            Find deals
          </button>
          <button className="primary-button" type="button">
            Analyze holding
          </button>
        </div>
      </div>

      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Purchase basis"
          value={currency(holding.cost_basis, holding.currency)}
        />
        <MetricCard
          label="Estimated value"
          tone="hold"
          value={currency(holding.current_total_value, holding.currency)}
        />
        <MetricCard
          label="Gain / loss"
          tone={
            Number(holding.unrealized_gain_loss ?? 0) >= 0 ? "good" : "watch"
          }
          value={`${signedCurrency(holding.unrealized_gain_loss)} (${percent(holding.unrealized_gain_loss_percent)})`}
        />
        <MetricCard
          label="Confidence"
          tone="watch"
          value={holding.valuation_confidence?.toUpperCase() ?? "--"}
        />
        <MetricCard
          label="Portfolio share"
          value={percent(detail.portfolio_share_percent)}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_0.9fr]">
        <Card>
          <h3 className="text-lg font-bold text-[var(--color-text)]">
            Marketplace value history
          </h3>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Fair-market snapshots for your holding’s condition.
          </p>
          <div className="mt-4">
            <ValueHistoryChart points={history} />
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[var(--color-text-muted)]">
            {history.map((snapshot) => (
              <span key={`${snapshot.marketplace}-${snapshot.timestamp}`}>
                {snapshot.marketplace}:{" "}
                {currency(snapshot.value, snapshot.currency)} ·{" "}
                {new Date(snapshot.timestamp).toLocaleDateString()}
              </span>
            ))}
          </div>
        </Card>
        <Card>
          <h3 className="text-lg font-bold text-[var(--color-text)]">
            Concentration risk
          </h3>
          <p className={`mt-3 text-2xl font-black capitalize ${riskTone}`}>
            {detail.concentration_risk.level}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
            {detail.concentration_risk.message}
          </p>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt>Portfolio value</dt>
              <dd>
                {currency(detail.portfolio_total_value, holding.currency)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Value rank</dt>
              <dd>
                {detail.concentration_risk.value_rank
                  ? `#${detail.concentration_risk.value_rank}`
                  : "--"}
              </dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card className="mt-5">
        <h3 className="text-lg font-bold text-[var(--color-text)]">
          Condition price comparison
        </h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {detail.condition_pricing.map((price) => (
            <div
              className="rounded-[var(--radius-control)] border border-[var(--color-border-soft)] p-4"
              key={price.condition}
            >
              <p className="text-sm font-bold capitalize">{price.condition}</p>
              <p className="mt-2 text-xl font-black">
                {currency(price.estimated_unit_value, holding.currency)}
              </p>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                {price.confidence
                  ? `${price.confidence} confidence`
                  : "No current data"}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="mt-5">
        <h3 className="text-lg font-bold text-[var(--color-text)]">
          Purchase details & notes
        </h3>
        <form className="mt-4 grid gap-4 md:grid-cols-3" onSubmit={saveDetails}>
          <TextField
            label="Purchase price"
            min="0"
            onChange={(event) => setPurchasePrice(event.target.value)}
            step="0.01"
            type="number"
            value={purchasePrice}
          />
          <TextField
            label="Purchase date"
            onChange={(event) => setPurchaseDate(event.target.value)}
            type="date"
            value={purchaseDate}
          />
          <TextField
            containerClassName="md:col-span-3"
            label="Notes"
            onChange={(event) => setNotes(event.target.value)}
            value={notes}
          />
          <div className="md:col-span-3">
            <button
              className="primary-button"
              disabled={updateMutation.isPending}
              type="submit"
            >
              {updateMutation.isPending ? "Saving..." : "Save purchase details"}
            </button>
            {updateMutation.error ? (
              <p className="mt-2 text-sm semantic-loss">
                {updateMutation.error}
              </p>
            ) : null}
          </div>
        </form>
      </Card>
    </section>
  );
}
