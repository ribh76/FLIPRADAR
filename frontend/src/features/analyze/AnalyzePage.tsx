import type { FormEvent } from "react";
import { useState } from "react";
import { apiClient } from "../../services/apiClient";
import { useServerMutation } from "../../hooks/serverState";
import {
  Card,
  CardHeader,
  CardTitle,
  FormAlert,
  MetricCard,
  SelectField,
  StatusBadge,
  TextField,
  verdictTone,
} from "../../components/ui";
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  Condition,
  UserGoal,
} from "../../types";
import { currency, numberValue } from "../../utils/format";

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
      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Card>
          <form className="space-y-5" onSubmit={handleSubmit}>
            <CardHeader>
              <CardTitle>Inputs</CardTitle>
            </CardHeader>
            <TextField
              label="Set number"
              onChange={(event) => setSetNumber(event.target.value)}
              placeholder="75192-1"
              required
              value={setNumber}
            />
            <SelectField
              label="Goal"
              onChange={(event) => setUserGoal(event.target.value as UserGoal)}
              value={userGoal}
            >
              <option value="buy_vs_pass">Buy or Pass</option>
              <option value="hold_vs_sell">Sell or Hold</option>
              <option value="hold">General Recommendation</option>
            </SelectField>
            <TextField
              label="Asking price"
              min="0"
              onChange={(event) => setAskingPrice(event.target.value)}
              placeholder="425.00"
              step="0.01"
              type="number"
              value={askingPrice}
            />
            <SelectField
              label="Condition"
              onChange={(event) =>
                setCondition(event.target.value as Condition)
              }
              value={condition}
            >
              <option value="new">New</option>
              <option value="used">Used</option>
              <option value="sealed">Sealed</option>
              <option value="unknown">Unknown</option>
            </SelectField>
            <FormAlert>{analyzeMutation.error}</FormAlert>
            <button
              className="primary-button w-full"
              disabled={analyzeMutation.isPending}
              type="submit"
            >
              {analyzeMutation.isPending ? "Analyzing..." : "Analyze"}
            </button>
          </form>
        </Card>

        <section className="space-y-5">
          <div className="page-card">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="metric-label">Main verdict</p>
                <h2 className="mt-2 text-2xl font-bold text-[var(--color-text)]">
                  {result?.set_number ?? "Waiting for set"}
                </h2>
              </div>
              <StatusBadge value={verdict} />
            </div>
            <div
              className={`rounded-[var(--radius-card)] border p-8 text-center ${result ? verdictTone(verdict) : "border-[var(--color-border-soft)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]"}`}
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
            <h2 className="text-lg font-bold text-[var(--color-text)]">
              Formatted explanation
            </h2>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-[var(--color-text-muted)]">
              {result?.reasoning ??
                "Run an analysis to see how fair value, asking price, confidence, and listing depth shaped the recommendation."}
            </p>
          </div>
        </section>
      </div>
    </section>
  );
}
