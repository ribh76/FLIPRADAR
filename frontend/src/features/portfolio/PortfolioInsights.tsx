import { AlertTriangle, Boxes, Calculator, Search, Tag } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  Card,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  PageState,
} from "../../components/ui";
import type { PortfolioHistory, PortfolioItem } from "../../types";
import { currency, signedCurrency } from "../../utils/format";

type HistoryRange = PortfolioHistory["range"];

const ranges: { label: string; value: HistoryRange }[] = [
  { label: "1D", value: "1d" },
  { label: "1W", value: "1w" },
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "180D", value: "180d" },
  { label: "1Y", value: "1y" },
  { label: "All", value: "all" },
];

function allocation(items: PortfolioItem[], field: "theme" | "condition") {
  const totals = new Map<string, number>();
  for (const item of items) {
    const key = item[field] || "Uncategorized";
    totals.set(
      key,
      (totals.get(key) ?? 0) +
        Number(item.current_total_value ?? item.cost_basis),
    );
  }
  return [...totals.entries()].sort(([, left], [, right]) => right - left);
}

export function PortfolioInsights({
  history,
  historyError,
  hasPartialHoldings,
  isHoldingsLoading,
  isHistoryLoading,
  items,
  onRangeChange,
  onRetryHistory,
  range,
}: {
  history?: PortfolioHistory;
  historyError: string;
  hasPartialHoldings: boolean;
  isHoldingsLoading: boolean;
  isHistoryLoading: boolean;
  items: PortfolioItem[];
  onRangeChange: (range: HistoryRange) => void;
  onRetryHistory: () => void;
  range: HistoryRange;
}) {
  const points =
    history?.points.map((point) => ({
      ...point,
      label: new Date(point.timestamp).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
      marketValue: Number(point.market_value),
      costBasis: Number(point.cost_basis),
    })) ?? [];
  const ranked = [...items]
    .filter((item) => item.unrealized_gain_loss !== null)
    .sort(
      (left, right) =>
        Number(right.unrealized_gain_loss) - Number(left.unrealized_gain_loss),
    );
  const warnings = items.filter(
    (item) =>
      item.valuation_status !== "valued" || item.valuation_confidence === "low",
  );
  const themeAllocation = allocation(items, "theme");
  const conditionAllocation = allocation(items, "condition");
  const firstPoint = points[0];
  const latestPoint = points[points.length - 1];

  return (
    <>
      <Card className="mb-5">
        <CardHeader
          action={
            <div
              aria-label="History range"
              className="flex flex-wrap gap-1"
              role="group"
            >
              {ranges.map((option) => (
                <button
                  className={
                    range === option.value
                      ? "primary-button px-2 py-1 text-xs"
                      : "secondary-button px-2 py-1 text-xs"
                  }
                  key={option.value}
                  aria-pressed={range === option.value}
                  onClick={() => onRangeChange(option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        >
          <CardTitle>Portfolio value history</CardTitle>
        </CardHeader>
        <div className="mt-4 h-72">
          {isHistoryLoading ? (
            <LoadingState title="Loading valuation history..." />
          ) : historyError ? (
            <ErrorState
              message={historyError}
              onRetry={onRetryHistory}
              title="History unavailable"
            />
          ) : points.length === 0 ? (
            <EmptyState
              message="Snapshots will appear as portfolio valuations are recorded."
              title="No valuation history yet"
            />
          ) : (
            <figure
              className="h-full"
              aria-label="Portfolio value history chart"
            >
              <ResponsiveContainer height="100%" width="100%">
                <AreaChart data={points}>
                  <CartesianGrid
                    stroke="var(--color-border-soft)"
                    strokeDasharray="3 3"
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                  />
                  <YAxis
                    tickFormatter={(value: number | string) => `$${value}`}
                    tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                    width={62}
                  />
                  <Tooltip
                    formatter={(value) =>
                      currency(
                        Number(Array.isArray(value) ? value[0] : (value ?? 0)),
                      )
                    }
                  />
                  <Area
                    dataKey="costBasis"
                    fill="rgba(235,136,30,0.12)"
                    name="Cost basis"
                    stroke="var(--color-accent-warm)"
                    type="monotone"
                  />
                  <Area
                    dataKey="marketValue"
                    fill="rgba(73,252,226,0.12)"
                    name="Market value"
                    stroke="var(--color-accent)"
                    type="monotone"
                  />
                </AreaChart>
              </ResponsiveContainer>
              <figcaption className="sr-only">
                {points.length} valuation snapshots. Market value changed from{" "}
                {currency(firstPoint.marketValue)} to{" "}
                {currency(latestPoint?.marketValue ?? firstPoint.marketValue)};
                cost basis changed from {currency(firstPoint.costBasis)} to{" "}
                {currency(latestPoint?.costBasis ?? firstPoint.costBasis)}.
              </figcaption>
            </figure>
          )}
        </div>
      </Card>
      {isHoldingsLoading ? (
        <div className="mb-5">
          <LoadingState title="Loading holding insights..." />
        </div>
      ) : items.length === 0 ? (
        <div className="mb-5">
          <EmptyState
            message="Add a holding to see performance and allocation insights."
            title="No holding insights yet"
          />
        </div>
      ) : hasPartialHoldings ? (
        <div className="mb-5">
          <PageState title="Partial portfolio data" tone="warning">
            Insights reflect the holdings on this page. Use filters or page
            through the portfolio to review the remaining holdings.
          </PageState>
        </div>
      ) : null}
      <div
        className="mb-5 grid gap-5 xl:grid-cols-3"
        data-testid="portfolio-insight-grid"
      >
        <InsightList title="Top performers" items={ranked.slice(0, 3)} />
        <InsightList
          title="Bottom performers"
          items={ranked.slice(-3).reverse()}
        />
        <InsightList
          title="Recently added"
          items={[...items]
            .sort((left, right) =>
              String(right.created_at).localeCompare(String(left.created_at)),
            )
            .slice(0, 3)}
        />
      </div>
      {warnings.length > 0 ? (
        <Card className="mb-5 border-[var(--color-accent-warm)]">
          <div className="flex gap-3">
            <AlertTriangle className="shrink-0 text-[var(--color-accent-warm)]" />
            <div>
              <CardTitle>Valuation needs attention</CardTitle>
              <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                {warnings.length} holding
                {warnings.length === 1 ? " has" : "s have"} stale, missing, or
                low-confidence market data. Refresh pricing before relying on
                totals.
              </p>
            </div>
          </div>
        </Card>
      ) : null}
      <div className="mb-5 grid gap-5 xl:grid-cols-3">
        <AllocationCard entries={themeAllocation} title="Theme allocation" />
        <AllocationCard
          entries={conditionAllocation}
          title="Condition allocation"
        />
        <QuickActions />
      </div>
    </>
  );
}

function InsightList({
  items,
  title,
}: {
  items: PortfolioItem[];
  title: string;
}) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--color-text-muted)]">
          No valued holdings available.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div
              className="flex items-center justify-between gap-3 text-sm"
              key={item.id}
            >
              <span className="min-w-0 truncate font-semibold">
                {item.set_number} · {item.set_name ?? "Unknown set"}
              </span>
              <span className="shrink-0 font-bold">
                {title === "Recently added"
                  ? (item.purchase_date?.slice(0, 10) ?? "--")
                  : signedCurrency(item.unrealized_gain_loss)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function AllocationCard({
  entries,
  title,
}: {
  entries: [string, number][];
  title: string;
}) {
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--color-text-muted)]">
          No holdings loaded.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {entries.slice(0, 5).map(([label, value]) => (
            <div key={label}>
              <div className="mb-1 flex justify-between gap-2 text-sm">
                <span className="capitalize">{label}</span>
                <span>
                  {total ? `${Math.round((value / total) * 100)}%` : "0%"}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-[var(--color-surface-muted)]">
                <div
                  className="h-full bg-[var(--color-accent)]"
                  style={{ width: `${total ? (value / total) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function QuickActions() {
  const actions = [
    ["Portfolio", "/portfolio", Boxes],
    ["Lookup", "/sets", Search],
    ["Deals", "/sets", Tag],
    ["Analysis", "/analyze", Calculator],
  ] as const;
  return (
    <Card>
      <CardTitle>Quick actions</CardTitle>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {actions.map(([label, to, Icon]) => (
          <Link
            className="secondary-button flex items-center justify-center gap-2"
            key={label}
            to={to}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </div>
    </Card>
  );
}
