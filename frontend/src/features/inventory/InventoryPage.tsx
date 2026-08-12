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
import { currency } from "../../utils/format";

export function InventoryPage() {
  const [setNumber, setSetNumber] = useState("75192");
  const [replacementQuery, setReplacementQuery] = useState("");
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
  const addToPurchaseList = useServerMutation(
    () => apiClient.inventory.addToPurchaseList(setNumber),
    { onSuccess: () => void checklist.refetch() },
  );
  const updatePurchase = useServerMutation(
    ({
      id,
      purchased,
      cost,
    }: {
      id: string;
      purchased: boolean;
      cost: number | null;
    }) =>
      apiClient.inventory.updatePurchaseItem(id, {
        purchased,
        actual_unit_cost: cost,
      }),
    { onSuccess: () => void checklist.refetch() },
  );
  const replacementSearch = useServerQuery(
    ["replacement-part-search", replacementQuery],
    () => apiClient.parts.search(replacementQuery),
    { enabled: replacementQuery.length > 1 },
  );

  function exportChecklist() {
    if (!checklist.data) return;
    const rows = [
      [
        "Part number",
        "Part",
        "Color",
        "Required",
        "Owned",
        "Missing",
        "Estimated unit cost",
        "Purchased",
      ],
      ...checklist.data.lines.map((line) => [
        line.element.part_number,
        line.element.part_name,
        line.substitute_element?.color ?? line.element.color,
        line.adjusted_quantity,
        line.owned_quantity,
        line.missing_quantity,
        (line.substitute_element ?? line.element).estimated_unit_cost ?? "",
        line.purchased ? "Yes" : "No",
      ]),
    ];
    const csv = rows
      .map((row) =>
        row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","),
      )
      .join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${checklist.data.set_number}-replacement-list.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

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
        <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            label="Required"
            value={String(checklist.data.required_parts)}
          />
          <MetricCard
            label="Complete"
            tone="hold"
            value={`${checklist.data.completeness_percent}%`}
          />
          <MetricCard
            label="Replacement estimate"
            tone="watch"
            value={currency(checklist.data.estimated_replacement_cost)}
          />
          <MetricCard
            label="Completed value"
            value={currency(checklist.data.completed_set_value)}
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
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Replacement plan</h2>
            <p className="text-sm text-[var(--color-text-muted)]">
              Completion-adjusted value{" "}
              {currency(checklist.data?.completeness_adjusted_value)} · Purchase
              price {currency(checklist.data?.purchase_price)} · Projected net{" "}
              {currency(checklist.data?.projected_net_value)}
            </p>
          </div>
          <div className="flex gap-2 print:hidden">
            <button
              className="secondary-button"
              type="button"
              onClick={exportChecklist}
            >
              Export CSV
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => window.print()}
            >
              Print list
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => addToPurchaseList.mutate({})}
            >
              Add missing to purchase list
            </button>
          </div>
        </div>
      </Card>
      <Card className="print:hidden">
        <TextField
          label="Search replacement parts"
          value={replacementQuery}
          onChange={(event) => setReplacementQuery(event.target.value)}
          placeholder="Part number or name"
        />
        {replacementSearch.data ? (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {replacementSearch.data.results.map((part) => (
              <div
                className="rounded border border-[var(--color-border)] p-3"
                key={part.id}
              >
                <strong>{part.name}</strong>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {part.canonical_identifier} · estimated{" "}
                  {currency(part.market_price)}
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </Card>
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
              {line.purchase_item_id ? (
                <div className="mt-3 flex items-center gap-3 print:hidden">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={line.purchased}
                      onChange={(event) =>
                        updatePurchase.mutate({
                          id: line.purchase_item_id!,
                          purchased: event.target.checked,
                          cost: line.actual_unit_cost,
                        })
                      }
                    />{" "}
                    Purchased
                  </label>
                  <label className="text-sm">
                    Actual unit cost
                    <input
                      className="ml-2 w-20 rounded border bg-transparent p-1"
                      type="number"
                      min="0"
                      step="0.01"
                      defaultValue={line.actual_unit_cost ?? ""}
                      onBlur={(event) =>
                        updatePurchase.mutate({
                          id: line.purchase_item_id!,
                          purchased: line.purchased,
                          cost:
                            event.target.value === ""
                              ? null
                              : Number(event.target.value),
                        })
                      }
                    />
                  </label>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}
