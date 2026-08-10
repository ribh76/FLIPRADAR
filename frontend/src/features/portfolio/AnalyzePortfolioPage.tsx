import {
  AlertTriangle,
  ArrowUpRight,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  Card,
  CardHeader,
  CardTitle,
  DataTable,
  EmptyState,
  FormAlert,
  MetricCard,
  PageState,
  SelectField,
  StatusBadge,
} from "../../components/ui";
import { useServerMutation, useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import type {
  PortfolioAnalysis,
  PortfolioAnalysisComparison,
  PortfolioAnalysisHistoryEntry,
  PortfolioItemRecommendation,
} from "../../types";
import { currency, numberValue, percent } from "../../utils/format";

type SortKey = "priority" | "label" | "confidence" | "set";

const labelCopy: Record<PortfolioItemRecommendation["label"], string> = {
  consider_selling: "Consider selling",
  hold: "Hold",
  insufficient_data: "Insufficient data",
  watch: "Watch",
};

function labelStatus(label: PortfolioItemRecommendation["label"]): string {
  if (label === "consider_selling") return "SELL";
  if (label === "insufficient_data") return "PASS";
  return label.toUpperCase();
}

function confidenceTone(confidence: string) {
  return confidence === "high"
    ? "good"
    : confidence === "low"
      ? "bad"
      : "watch";
}

function analysisRows(
  recommendations: PortfolioItemRecommendation[],
  sort: SortKey,
) {
  const confidenceRank = { high: 3, medium: 2, low: 1 };
  return [...recommendations].sort((left, right) => {
    if (sort === "set") return left.set_number.localeCompare(right.set_number);
    if (sort === "label") return left.label.localeCompare(right.label);
    if (sort === "confidence") {
      return confidenceRank[right.confidence] - confidenceRank[left.confidence];
    }
    return left.priority - right.priority;
  });
}

function NarrativeObservations({ analysis }: { analysis: PortfolioAnalysis }) {
  const narrative = analysis.ai_narrative;
  if (!narrative) {
    return (
      <PageState title="Deterministic analysis ready" tone="neutral">
        The portfolio metrics, risks, and item labels are available. The
        optional AI narrative is{" "}
        {analysis.ai_narrative_status.replace(/_/g, " ")}.
      </PageState>
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <CardTitle>Diversification observations</CardTitle>
        <ObservationList
          emptyMessage="No diversification observation was generated."
          observations={narrative.diversification_observations}
        />
      </Card>
      <Card>
        <CardTitle>Concentration observations</CardTitle>
        <ObservationList
          emptyMessage="No concentration observation was generated."
          observations={narrative.concentration_observations}
        />
      </Card>
    </div>
  );
}

function ObservationList({
  emptyMessage,
  observations,
}: {
  emptyMessage: string;
  observations: Array<{ source_metric: string; text: string }>;
}) {
  if (observations.length === 0) {
    return (
      <p className="mt-3 text-sm text-[var(--color-text-muted)]">
        {emptyMessage}
      </p>
    );
  }
  return (
    <div className="mt-4 space-y-3">
      {observations.map((observation) => (
        <div
          className="rounded-[var(--radius-control)] border border-[var(--color-border-soft)] p-3"
          key={`${observation.source_metric}-${observation.text}`}
        >
          <p className="text-sm text-[var(--color-text-muted)]">
            {observation.text}
          </p>
        </div>
      ))}
    </div>
  );
}

export function AnalyzePortfolioPage() {
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [sort, setSort] = useState<SortKey>("priority");
  const [previousAnalysisId, setPreviousAnalysisId] = useState("");
  const [currentAnalysisId, setCurrentAnalysisId] = useState("");
  const [comparison, setComparison] =
    useState<PortfolioAnalysisComparison | null>(null);
  const historyQuery = useServerQuery(
    ["portfolio-analysis-history"],
    useCallback(() => apiClient.portfolio.analyses(), []),
  );
  const analyzeMutation = useServerMutation(apiClient.portfolio.analyze, {
    onSuccess: async (result) => {
      setAnalysis(result);
      await historyQuery.refetch();
    },
  });
  const compareMutation = useServerMutation(
    ({ previousId, currentId }: { previousId: string; currentId: string }) =>
      apiClient.portfolio.compareAnalyses(previousId, currentId),
    { onSuccess: (result) => setComparison(result) },
  );
  const rows = useMemo(
    () => analysisRows(analysis?.item_recommendations ?? [], sort),
    [analysis, sort],
  );
  const summary = analysis?.analytics.summary_metrics;
  const opportunityCount = analysis?.item_recommendations.filter(
    (item) => item.label === "consider_selling" || item.label === "watch",
  ).length;
  const history = historyQuery.data?.data ?? [];

  const columns = [
    {
      header: "Priority",
      key: "priority",
      render: (item: PortfolioItemRecommendation) => `#${item.priority}`,
    },
    {
      header: "Holding",
      key: "holding",
      render: (item: PortfolioItemRecommendation) => (
        <div>
          <Link
            className="font-bold text-[var(--color-text)] hover:text-[var(--color-accent-warm)]"
            to={`/portfolio/items/${item.portfolio_item_id}`}
          >
            {item.set_number}
          </Link>
          <div className="text-xs text-[var(--color-text-muted)]">
            {item.set_name ?? "Unknown set"}
          </div>
        </div>
      ),
    },
    {
      header: "Label",
      key: "label",
      render: (item: PortfolioItemRecommendation) => (
        <div className="space-y-1">
          <StatusBadge value={labelStatus(item.label)} />
          <div className="text-xs text-[var(--color-text-muted)]">
            {labelCopy[item.label]}
          </div>
        </div>
      ),
    },
    {
      header: "Confidence",
      key: "confidence",
      render: (item: PortfolioItemRecommendation) => (
        <span
          className={`font-bold capitalize ${
            item.confidence === "low"
              ? "semantic-loss"
              : item.confidence === "high"
                ? "semantic-gain"
                : "text-[var(--color-accent-warm)]"
          }`}
        >
          {item.confidence}
        </span>
      ),
    },
    {
      header: "Evidence notes",
      key: "notes",
      render: (item: PortfolioItemRecommendation) => (
        <div className="space-y-1 text-xs text-[var(--color-text-muted)]">
          <div>
            {item.reason_codes
              .map((code) => code.replace(/_/g, " "))
              .join(", ")}
          </div>
          {item.data_quality_flags.length > 0 ? (
            <div className="text-[var(--color-accent-warm)]">
              {item.data_quality_flags
                .map((flag) => flag.replace(/_/g, " "))
                .join(", ")}
            </div>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <section className="space-y-5">
      <Card className="border-[var(--color-accent)] bg-[rgba(73,252,226,0.06)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <CardTitle>Portfolio analysis</CardTitle>
            <p className="mt-2 max-w-2xl text-sm text-[var(--color-text-muted)]">
              Refresh your calculated portfolio metrics, risks, opportunities,
              and item-level actions. Each run is saved to your account.
            </p>
          </div>
          <button
            className="primary-button"
            disabled={analyzeMutation.isPending}
            onClick={() => void analyzeMutation.mutate(undefined)}
            type="button"
          >
            <RefreshCw
              className={analyzeMutation.isPending ? "animate-spin" : ""}
              size={17}
            />
            {analyzeMutation.isPending ? "Analyzing..." : "Analyze portfolio"}
          </button>
        </div>
      </Card>

      {analyzeMutation.error ? (
        <FormAlert>{analyzeMutation.error}</FormAlert>
      ) : null}

      {!analysis && !analyzeMutation.isPending ? (
        <EmptyState
          message="Run an analysis to see portfolio-wide observations and prioritized holding recommendations."
          title="Ready to analyze your portfolio"
        />
      ) : null}

      {analysis ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Market value"
              tone="hold"
              value={currency(
                analysis.analytics.total_market_value,
                analysis.analytics.currency,
              )}
            />
            <MetricCard
              label="Cost basis"
              value={currency(
                analysis.analytics.total_cost_basis,
                analysis.analytics.currency,
              )}
            />
            <MetricCard
              label="Valuation coverage"
              tone="watch"
              value={`${analysis.analytics.valued_holding_count}/${analysis.analytics.holding_count}`}
            />
            <MetricCard
              label="Overall confidence"
              tone={confidenceTone(analysis.confidence_summary.overall)}
              value={analysis.confidence_summary.overall.toUpperCase()}
            />
            <MetricCard
              label="Concentration"
              tone={summary?.concentration.level === "high" ? "bad" : "watch"}
              value={summary?.concentration.level.toUpperCase() ?? "--"}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Executive summary</CardTitle>
            </CardHeader>
            <p className="text-sm leading-7 text-[var(--color-text-muted)]">
              {analysis.ai_narrative?.executive_summary ??
                "This completed analysis uses the current deterministic portfolio metrics and item-level labels. Review confidence and data-quality warnings before acting."}
            </p>
            <p className="mt-3 text-xs text-[var(--color-text-muted)]">
              Generated {new Date(analysis.generated_at).toLocaleString()}
              {analysis.ai_narrative
                ? ` · AI narrative ${analysis.ai_narrative.prompt_version}`
                : " · Deterministic result"}
            </p>
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            <Card>
              <CardTitle>Portfolio-wide opportunities</CardTitle>
              <p className="mt-3 text-sm text-[var(--color-text-muted)]">
                {numberValue(opportunityCount)} holdings are labelled for a
                closer review or monitoring. Top calculated performers are
                listed below.
              </p>
              <div className="mt-4 space-y-2">
                {summary?.top_performers.length ? (
                  summary.top_performers.slice(0, 3).map((holding) => (
                    <div
                      className="flex items-center justify-between gap-3 text-sm"
                      key={holding.set_number}
                    >
                      <span className="font-semibold">
                        {holding.set_number} ·{" "}
                        {holding.set_name ?? "Unknown set"}
                      </span>
                      <ArrowUpRight
                        className="text-[var(--color-accent)]"
                        size={17}
                      />
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">
                    No valued performers are available yet.
                  </p>
                )}
              </div>
            </Card>
            <Card className="border-[var(--color-accent-warm)]">
              <CardTitle>Portfolio-wide risks</CardTitle>
              <p className="mt-3 text-sm text-[var(--color-text-muted)]">
                Largest holding:{" "}
                {percent(summary?.concentration.largest_holding_percent)}. Top
                three holdings:{" "}
                {percent(summary?.concentration.top_three_percent)}.
              </p>
              <div className="mt-4 space-y-2">
                {analysis.data_quality_warnings.map((warning) => (
                  <div className="flex gap-2 text-sm" key={warning.code}>
                    <ShieldAlert
                      className="mt-0.5 shrink-0 text-[var(--color-accent-warm)]"
                      size={16}
                    />
                    <span>
                      {warning.message} ({warning.affected_holding_count})
                    </span>
                  </div>
                ))}
                {analysis.data_quality_warnings.length === 0 ? (
                  <p className="text-sm text-[var(--color-text-muted)]">
                    No deterministic data-quality warnings were found.
                  </p>
                ) : null}
              </div>
            </Card>
          </div>

          <NarrativeObservations analysis={analysis} />

          <Card>
            <CardTitle>Prioritized actions</CardTitle>
            {analysis.ai_narrative?.prioritized_actions.length ? (
              <div className="mt-4 space-y-3">
                {analysis.ai_narrative.prioritized_actions.map((action) => (
                  <div
                    className="flex items-start gap-3 rounded-[var(--radius-control)] border border-[var(--color-border-soft)] p-3"
                    key={`${action.item_key}-${action.priority}`}
                  >
                    <span className="rounded-full bg-[var(--color-surface-muted)] px-2 py-1 text-xs font-bold">
                      #{action.priority}
                    </span>
                    <div>
                      <StatusBadge value={labelStatus(action.label)} />
                      <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                        {action.text}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-[var(--color-text-muted)]">
                Use the deterministic item recommendations below, ordered by
                priority.
              </p>
            )}
          </Card>

          <Card className="overflow-hidden p-0">
            <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border-soft)] p-5">
              <div>
                <CardTitle>Item recommendations</CardTitle>
                <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                  Rule-derived labels, confidence, and evidence notes.
                </p>
              </div>
              <SelectField
                label="Sort recommendations"
                onChange={(event) => setSort(event.target.value as SortKey)}
                value={sort}
              >
                <option value="priority">Priority</option>
                <option value="label">Recommendation</option>
                <option value="confidence">Confidence</option>
                <option value="set">Set number</option>
              </SelectField>
            </div>
            <DataTable
              columns={columns}
              emptyMessage="No portfolio holdings were available for this analysis."
              getRowKey={(item) => item.portfolio_item_id}
              minWidth="920px"
              rows={rows}
            />
          </Card>
        </>
      ) : null}

      <PortfolioAnalysisHistory
        comparison={comparison}
        currentAnalysisId={currentAnalysisId}
        error={historyQuery.error || compareMutation.error}
        history={history}
        isComparing={compareMutation.isPending}
        isLoading={historyQuery.isLoading}
        onCompare={() =>
          void compareMutation.mutate({
            previousId: previousAnalysisId,
            currentId: currentAnalysisId,
          })
        }
        onCurrentAnalysisChange={setCurrentAnalysisId}
        onPreviousAnalysisChange={setPreviousAnalysisId}
        previousAnalysisId={previousAnalysisId}
      />

      <PageState
        icon={<AlertTriangle size={20} />}
        title="Collectibles-market disclaimer"
        tone="warning"
      >
        Portfolio valuations and recommendations are estimates based on
        available market data. They are not financial advice, do not guarantee
        resale value or liquidity, and may not reflect fees, condition, demand,
        or realised sale proceeds.
      </PageState>
    </section>
  );
}

function PortfolioAnalysisHistory({
  comparison,
  currentAnalysisId,
  error,
  history,
  isComparing,
  isLoading,
  onCompare,
  onCurrentAnalysisChange,
  onPreviousAnalysisChange,
  previousAnalysisId,
}: {
  comparison: PortfolioAnalysisComparison | null;
  currentAnalysisId: string;
  error: string;
  history: PortfolioAnalysisHistoryEntry[];
  isComparing: boolean;
  isLoading: boolean;
  onCompare: () => void;
  onCurrentAnalysisChange: (id: string) => void;
  onPreviousAnalysisChange: (id: string) => void;
  previousAnalysisId: string;
}) {
  const historyColumns = [
    {
      header: "Analysis date",
      key: "date",
      render: (entry: PortfolioAnalysisHistoryEntry) => (
        <div>
          <strong>{new Date(entry.generated_at).toLocaleString()}</strong>
          <div className="text-xs text-[var(--color-text-muted)]">
            {entry.method_version} · {entry.prompt_version}
          </div>
        </div>
      ),
    },
    {
      header: "Confidence",
      key: "confidence",
      render: (entry: PortfolioAnalysisHistoryEntry) => (
        <span className="capitalize">{entry.confidence_summary.overall}</span>
      ),
    },
    {
      header: "Recommendations",
      key: "recommendations",
      render: (entry: PortfolioAnalysisHistoryEntry) =>
        `${entry.item_recommendations.length} holdings`,
    },
    {
      header: "Data warnings",
      key: "warnings",
      render: (entry: PortfolioAnalysisHistoryEntry) =>
        entry.data_quality_warnings.length || "None",
    },
  ];

  return (
    <section className="space-y-5">
      <Card className="overflow-hidden p-0">
        <div className="border-b border-[var(--color-border-soft)] p-5">
          <CardTitle>Previous analyses</CardTitle>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Each entry preserves its method, prompt, recommendations, and
            portfolio context at the time it was generated.
          </p>
        </div>
        <DataTable
          columns={historyColumns}
          emptyMessage={
            isLoading
              ? "Loading completed analyses..."
              : "Run an analysis to start your history."
          }
          getRowKey={(entry) => entry.id}
          isLoading={isLoading}
          minWidth="720px"
          rows={history}
        />
      </Card>

      {history.length >= 2 ? (
        <Card>
          <CardHeader>
            <CardTitle>Compare recommendation changes</CardTitle>
          </CardHeader>
          <p className="text-sm text-[var(--color-text-muted)]">
            Compare two completed analyses to see how each set's recommendation
            changed over time.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <SelectField
              label="Earlier analysis"
              onChange={(event) => onPreviousAnalysisChange(event.target.value)}
              value={previousAnalysisId}
            >
              <option value="">Select an analysis</option>
              {history.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {new Date(entry.generated_at).toLocaleString()}
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Later analysis"
              onChange={(event) => onCurrentAnalysisChange(event.target.value)}
              value={currentAnalysisId}
            >
              <option value="">Select an analysis</option>
              {history.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {new Date(entry.generated_at).toLocaleString()}
                </option>
              ))}
            </SelectField>
          </div>
          <button
            className="primary-button mt-4"
            disabled={
              isComparing ||
              !previousAnalysisId ||
              !currentAnalysisId ||
              previousAnalysisId === currentAnalysisId
            }
            onClick={onCompare}
            type="button"
          >
            Compare analyses
          </button>
          {error ? <FormAlert>{error}</FormAlert> : null}
        </Card>
      ) : null}

      {comparison ? (
        <Card className="overflow-hidden p-0">
          <div className="border-b border-[var(--color-border-soft)] p-5">
            <CardTitle>Recommendation changes by set</CardTitle>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              {new Date(comparison.previous_generated_at).toLocaleString()} to{" "}
              {new Date(comparison.current_generated_at).toLocaleString()}
            </p>
          </div>
          <DataTable
            columns={[
              {
                header: "Set",
                key: "set",
                render: (change) =>
                  `${change.set_number} · ${change.set_name ?? "Unknown set"}`,
              },
              {
                header: "Previous",
                key: "previous",
                render: (change) => change.previous_label ?? "Not held",
              },
              {
                header: "Current",
                key: "current",
                render: (change) => change.current_label ?? "Removed",
              },
              {
                header: "Change",
                key: "change",
                render: (change) => (
                  <span
                    className={
                      change.is_reversal
                        ? "semantic-loss font-bold"
                        : "capitalize"
                    }
                  >
                    {change.is_reversal ? "Reversal" : change.change_type}
                  </span>
                ),
              },
            ]}
            emptyMessage="No holdings were available in either selected analysis."
            getRowKey={(change) => change.set_number}
            minWidth="720px"
            rows={comparison.changes}
          />
        </Card>
      ) : null}
    </section>
  );
}
