import type { FormEvent } from "react";
import { useCallback, useState } from "react";
import { apiClient } from "../api/client";
import {
  invalidateServerState,
  useServerMutation,
  useServerQuery,
} from "../api/serverState";
import { MetricCard } from "../components/MetricCard";
import type { Condition, PortfolioItemCreate } from "../types";
import { currency, signedCurrency } from "../utils/format";

const portfolioKey = ["portfolio"];
const portfolioSummaryKey = ["portfolio-summary"];

export function PortfolioPage() {
  const [setNumber, setSetNumber] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [purchasePrice, setPurchasePrice] = useState("");
  const [condition, setCondition] = useState<Condition>("new");
  const [acquiredAt, setAcquiredAt] = useState("");
  const [notes, setNotes] = useState("");
  const loadPortfolio = useCallback(() => apiClient.portfolio.list(), []);
  const loadSummary = useCallback(() => apiClient.portfolio.summary(), []);
  const itemsQuery = useServerQuery(portfolioKey, loadPortfolio);
  const summaryQuery = useServerQuery(portfolioSummaryKey, loadSummary);
  const refreshPortfolio = useCallback(async () => {
    invalidateServerState(portfolioKey);
    invalidateServerState(portfolioSummaryKey);
    await Promise.all([itemsQuery.refetch(), summaryQuery.refetch()]);
  }, [itemsQuery, summaryQuery]);
  const addMutation = useServerMutation(apiClient.portfolio.addItem, {
    onSuccess: async () => {
      setSetNumber("");
      setQuantity(1);
      setPurchasePrice("");
      setCondition("new");
      setAcquiredAt("");
      setNotes("");
      await refreshPortfolio();
    },
  });
  const deleteMutation = useServerMutation(apiClient.portfolio.deleteItem, {
    onSuccess: refreshPortfolio,
  });
  const items = itemsQuery.data?.data ?? [];
  const error =
    itemsQuery.error ||
    summaryQuery.error ||
    addMutation.error ||
    deleteMutation.error;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: PortfolioItemCreate = {
      set_number: setNumber,
      quantity,
      purchase_price: Number(purchasePrice),
      condition,
      acquired_at: acquiredAt ? new Date(acquiredAt).toISOString() : null,
      notes: notes || null,
    };
    void addMutation.mutate(payload);
  }

  return (
    <section>
      <div className="mb-7">
        <h1 className="text-3xl font-bold text-white">Portfolio</h1>
        <p className="mt-2 text-blue-100">
          Track your LEGO collection value, basis, and holdings.
        </p>
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm font-semibold text-red-800">
          {error}
        </div>
      ) : null}

      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total Portfolio Value"
          tone="hold"
          value={currency(summaryQuery.data?.estimated_current_value)}
        />
        <MetricCard
          label="Total Cost Basis"
          value={currency(summaryQuery.data?.total_cost_basis)}
        />
        <MetricCard
          label="Unrealized Gain/Loss"
          tone="good"
          value={signedCurrency(summaryQuery.data?.unrealized_gain_loss)}
        />
        <MetricCard
          label="Total Sets"
          tone="watch"
          value={String(summaryQuery.data?.total_quantity ?? 0)}
        />
      </div>

      <form className="page-card mb-5" onSubmit={handleSubmit}>
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-lg font-bold text-slate-950">Add item</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          <label className="space-y-2">
            <span className="field-label">Set number</span>
            <input
              className="field-input"
              onChange={(event) => setSetNumber(event.target.value)}
              required
              value={setNumber}
            />
          </label>
          <label className="space-y-2">
            <span className="field-label">Quantity</span>
            <input
              className="field-input"
              min="1"
              onChange={(event) => setQuantity(Number(event.target.value))}
              required
              type="number"
              value={quantity}
            />
          </label>
          <label className="space-y-2">
            <span className="field-label">Purchase price</span>
            <input
              className="field-input"
              min="0"
              onChange={(event) => setPurchasePrice(event.target.value)}
              required
              step="0.01"
              type="number"
              value={purchasePrice}
            />
          </label>
          <label className="space-y-2">
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
          <label className="space-y-2">
            <span className="field-label">Acquired date</span>
            <input
              className="field-input"
              onChange={(event) => setAcquiredAt(event.target.value)}
              type="date"
              value={acquiredAt}
            />
          </label>
          <label className="space-y-2 md:col-span-2 xl:col-span-1">
            <span className="field-label">Notes</span>
            <input
              className="field-input"
              onChange={(event) => setNotes(event.target.value)}
              value={notes}
            />
          </label>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            className="primary-button"
            disabled={addMutation.isPending}
            type="submit"
          >
            {addMutation.isPending ? "Adding..." : "Add item"}
          </button>
        </div>
      </form>

      <section className="page-card overflow-hidden p-0">
        <div className="border-b border-slate-200 p-5">
          <h2 className="text-lg font-bold text-slate-950">Holdings</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-normal text-slate-500">
              <tr>
                <th className="px-4 py-3">Set Number</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Condition</th>
                <th className="px-4 py-3">Quantity</th>
                <th className="px-4 py-3">Purchase Price</th>
                <th className="px-4 py-3">Current Value</th>
                <th className="px-4 py-3">Gain/Loss</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {itemsQuery.isLoading ? (
                <tr>
                  <td
                    className="px-4 py-8 text-center font-semibold text-slate-500"
                    colSpan={8}
                  >
                    Loading portfolio...
                  </td>
                </tr>
              ) : null}
              {!itemsQuery.isLoading && items.length === 0 ? (
                <tr>
                  <td
                    className="px-4 py-8 text-center font-semibold text-slate-500"
                    colSpan={8}
                  >
                    No holdings yet.
                  </td>
                </tr>
              ) : null}
              {items.map((item) => {
                const gain = Number(item.unrealized_gain_loss ?? 0);
                return (
                  <tr className="bg-white" key={item.id}>
                    <td className="px-4 py-3 font-bold text-slate-950">
                      {item.set_number}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {item.set_name ?? "--"}
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-700">
                      {item.condition}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {item.quantity}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {currency(item.purchase_price)}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {currency(item.current_total_value)}
                    </td>
                    <td
                      className={`px-4 py-3 font-bold ${gain >= 0 ? "text-emerald-700" : "text-red-700"}`}
                    >
                      {signedCurrency(item.unrealized_gain_loss)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="secondary-button"
                        disabled={deleteMutation.isPending}
                        onClick={() => void deleteMutation.mutate(item.id)}
                        type="button"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
