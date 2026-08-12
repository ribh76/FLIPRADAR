import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  ErrorState,
  LoadingState,
  MetricCard,
  TextField,
} from "../../components/ui";
import { useServerMutation, useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";

export function InventoryPage() {
  const [setNumber, setSetNumber] = useState("75192");
  const inventory = useServerQuery(["inventory"], apiClient.inventory.list);
  const update = useServerMutation(
    ({ elementId, quantity }: { elementId: string; quantity: number }) =>
      apiClient.inventory.setQuantity(elementId, quantity),
    { onSuccess: () => void inventory.refetch() },
  );
  const checklist = useServerQuery(
    ["missing-checklist", setNumber],
    () => apiClient.inventory.checklist(setNumber),
    { enabled: Boolean(setNumber) },
  );
  const adjust = useServerMutation(
    ({
      id,
      manual,
      substitute,
    }: {
      id: string;
      manual: number;
      substitute: string | null;
    }) =>
      apiClient.inventory.adjustChecklist(setNumber, id, {
        manual_adjustment: manual,
        substitute_element_id: substitute,
      }),
    { onSuccess: () => void checklist.refetch() },
  );

  return (
    <section className="space-y-5">
      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <TextField
              label="Build checklist set number"
              value={setNumber}
              onChange={(event) => setSetNumber(event.target.value.trim())}
            />
          </div>
          <Link className="secondary-button" to={`/sets/${setNumber}`}>
            View set
          </Link>
        </div>
      </Card>
      {checklist.data ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            label="Required"
            value={String(checklist.data.required_parts)}
          />
          <MetricCard
            label="Covered"
            tone="hold"
            value={String(checklist.data.owned_parts)}
          />
          <MetricCard
            label="Missing"
            tone="watch"
            value={String(checklist.data.missing_parts)}
          />
        </div>
      ) : null}
      <Card>
        <h2 className="text-lg font-bold">Your inventory</h2>
        {inventory.isLoading ? (
          <LoadingState title="Loading inventory..." />
        ) : null}
        {inventory.error ? (
          <ErrorState
            title="Inventory unavailable"
            message={inventory.error}
            onRetry={() => void inventory.refetch()}
          />
        ) : null}
        <div className="mt-4 space-y-3">
          {inventory.data?.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 rounded border border-[var(--color-border)] p-3"
            >
              <div>
                <strong>{item.element.part_name}</strong>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {item.element.part_number} · {item.element.color}
                </p>
              </div>
              <input
                aria-label={`Quantity for ${item.element.part_name} ${item.element.color}`}
                className="w-20 rounded border bg-transparent p-2 text-right"
                type="number"
                min="0"
                defaultValue={item.quantity}
                onBlur={(event) => {
                  const quantity = Number(event.target.value);
                  if (Number.isInteger(quantity) && quantity !== item.quantity)
                    update.mutate({ elementId: item.element.id, quantity });
                }}
              />
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="text-lg font-bold">Missing-parts checklist</h2>
        {checklist.isLoading ? (
          <LoadingState title="Generating checklist..." />
        ) : null}
        {checklist.error ? (
          <ErrorState
            title="Checklist unavailable"
            message={checklist.error}
            onRetry={() => void checklist.refetch()}
          />
        ) : null}
        <div className="mt-4 space-y-4">
          {checklist.data?.lines.map((line) => (
            <div
              className="rounded border border-[var(--color-border)] p-4"
              key={line.requirement_id}
            >
              <div className="flex justify-between gap-3">
                <div>
                  <strong>{line.element.part_name}</strong>
                  <p className="text-sm text-[var(--color-text-muted)]">
                    {line.element.part_number} · {line.element.color}
                  </p>
                </div>
                <strong
                  className={
                    line.missing_quantity
                      ? "text-[var(--color-accent-warm)]"
                      : "text-[var(--color-gain)]"
                  }
                >
                  {line.missing_quantity
                    ? `${line.missing_quantity} missing`
                    : "Covered"}
                </strong>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <label className="text-sm">
                  Manual adjustment
                  <input
                    className="mt-1 w-full rounded border bg-transparent p-2"
                    type="number"
                    defaultValue={
                      line.adjusted_quantity - line.required_quantity
                    }
                    onBlur={(event) =>
                      adjust.mutate({
                        id: line.requirement_id,
                        manual: Number(event.target.value) || 0,
                        substitute: line.substitute_element?.id ?? null,
                      })
                    }
                  />
                </label>
                <label className="text-sm">
                  Use substitute
                  <select
                    className="mt-1 w-full rounded border bg-transparent p-2"
                    value={line.substitute_element?.id ?? ""}
                    onChange={(event) =>
                      adjust.mutate({
                        id: line.requirement_id,
                        manual: line.adjusted_quantity - line.required_quantity,
                        substitute: event.target.value || null,
                      })
                    }
                  >
                    <option value="">Exact color</option>
                    {line.substitution_candidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.color}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}
