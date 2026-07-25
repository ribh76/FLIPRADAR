import type { FormEvent } from "react";
import { useState } from "react";
import { apiClient } from "../api/client";
import { useServerMutation } from "../api/serverState";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge, verdictTone } from "../components/StatusBadge";
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  Condition,
  UserGoal,
} from "../types";
import { currency, numberValue } from "../utils/format";

export function AnalyzePage() {
  const [setNumber, setSetNumber] = useState("");
  const [userGoal, setUserGoal] = useState<UserGoal>("buy_vs_pass");
  const [askingPrice, setAskingPrice] = useState("");
  const [condition, setCondition] = useState<Condition>("new");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const analyzeMutation = useServerMutation(apiClient.analyze, {
    onSuccess: (response) => setResult(response),
  });
  const verdict = result?.recommendation ?? "WATCH";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: AnalyzeRequest = {
      set_number: setNumber,
      user_goal: userGoal,
      condition,
      asking_price: askingPrice ? Number(askingPrice) : null,
    };
    void analyzeMutation.mutate(payload);
  }

  return (
    <section>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Analyze Set</h1>
          <p className="mt-2 text-blue-100">
            A calculator-style recommendation tool for LEGO set decisions.
          </p>
        </div>
        <div className="rounded-md bg-white/10 px-3 py-2 text-sm font-bold text-blue-100">
          BUY / PASS / HOLD / WATCH
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <form className="page-card space-y-5" onSubmit={handleSubmit}>
          <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
            <h2 className="text-lg font-bold text-slate-950">Inputs</h2>
          </div>
          <label className="block space-y-2">
            <span className="field-label">Set number</span>
            <input
              className="field-input"
              onChange={(event) => setSetNumber(event.target.value)}
              placeholder="75192-1"
              required
              value={setNumber}
            />
          </label>
          <label className="block space-y-2">
            <span className="field-label">Goal</span>
            <select
              className="field-input"
              onChange={(event) => setUserGoal(event.target.value as UserGoal)}
              value={userGoal}
            >
              <option value="buy_vs_pass">Buy or Pass</option>
              <option value="hold_vs_sell">Sell or Hold</option>
              <option value="hold">General Recommendation</option>
            </select>
          </label>
          <label className="block space-y-2">
            <span className="field-label">Asking price</span>
            <input
              className="field-input"
              min="0"
              onChange={(event) => setAskingPrice(event.target.value)}
              placeholder="425.00"
              step="0.01"
              type="number"
              value={askingPrice}
            />
          </label>
          <label className="block space-y-2">
            <span className="field-label">Condition</span>
            <select
              className="field-input"
              onChange={(event) =>
                setCondition(event.target.value as Condition)
              }
              value={condition}
            >
              <option value="new">New</option>
              <option value="used">Used</option>
              <option value="sealed">Sealed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          {analyzeMutation.error ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-800">
              {analyzeMutation.error}
            </div>
          ) : null}
          <button
            className="primary-button w-full"
            disabled={analyzeMutation.isPending}
            type="submit"
          >
            {analyzeMutation.isPending ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        <section className="space-y-5">
          <div className="page-card">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="metric-label">Main verdict</p>
                <h2 className="mt-2 text-2xl font-bold text-slate-950">
                  {result?.set_number ?? "Waiting for set"}
                </h2>
              </div>
              <StatusBadge value={verdict} />
            </div>
            <div
              className={`rounded-lg border p-8 text-center ${result ? verdictTone(verdict) : "border-slate-200 bg-slate-50 text-slate-600"}`}
            >
              <div className="text-6xl font-black tracking-normal">
                {result?.recommendation ?? "READY"}
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Fair Value"
              tone="hold"
              value={currency(result?.fair_value)}
            />
            <MetricCard
              label="Asking Price"
              value={currency(result?.asking_price)}
            />
            <MetricCard
              label="Score"
              value={result ? `${result.score}/100` : "--"}
            />
            <MetricCard
              label="Confidence"
              tone="watch"
              value={result?.confidence.toUpperCase() ?? "--"}
            />
            <MetricCard
              label="Market Low"
              value={currency(result?.market_low)}
            />
            <MetricCard
              label="Market High"
              value={currency(result?.market_high)}
            />
            <MetricCard
              label="Listing Count"
              value={numberValue(result?.listing_count)}
            />
            <MetricCard label="Condition" value={condition.toUpperCase()} />
          </div>

          <div className="page-card">
            <h2 className="text-lg font-bold text-slate-950">
              Formatted explanation
            </h2>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
              {result?.reasoning ??
                "Run an analysis to see how fair value, asking price, confidence, and listing depth shaped the recommendation."}
            </p>
          </div>
        </section>
      </div>
    </section>
  );
}
