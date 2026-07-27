import type { FormEvent } from "react";
import { useCallback, useState } from "react";
import { apiClient } from "../../services/apiClient";
import {
  invalidateServerState,
  useServerMutation,
  useServerQuery,
} from "../../hooks/serverState";
import {
  Card,
  CardHeader,
  CardTitle,
  ConfirmationDialog,
  DataTable,
  FormAlert,
  MetricCard,
  SelectField,
  TextField,
} from "../../components/ui";
import type {
  Condition,
  PortfolioItem,
  PortfolioItemCreate,
} from "../../types";
import { currency, signedCurrency } from "../../utils/format";

const portfolioKey = ["portfolio"];
const portfolioSummaryKey = ["portfolio-summary"];

export function PortfolioPage() {
  const [setNumber, setSetNumber] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [purchasePrice, setPurchasePrice] = useState("");
  const [condition, setCondition] = useState<Condition>("new");
  const [acquiredAt, setAcquiredAt] = useState("");
  const [notes, setNotes] = useState("");
  const [deleteCandidate, setDeleteCandidate] = useState<PortfolioItem | null>(
    null,
  );
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

  const columns = [
    {
      header: "Set Number",
      key: "set-number",
      render: (item: PortfolioItem) => (
        <span className="font-bold text-[var(--color-text)]">
          {item.set_number}
        </span>
      ),
    },
    {
      header: "Name",
      key: "name",
      render: (item: PortfolioItem) => (
        <span className="text-[var(--color-text-muted)]">
          {item.set_name ?? "--"}
        </span>
      ),
    },
    {
      header: "Condition",
      key: "condition",
      render: (item: PortfolioItem) => (
        <span className="capitalize text-[var(--color-text-muted)]">
          {item.condition}
        </span>
      ),
    },
    {
      header: "Quantity",
      key: "quantity",
      render: (item: PortfolioItem) => (
        <span className="text-[var(--color-text-muted)]">{item.quantity}</span>
      ),
    },
    {
      header: "Purchase Price",
      key: "purchase-price",
      render: (item: PortfolioItem) => (
        <span className="text-[var(--color-text-muted)]">
          {currency(item.purchase_price)}
        </span>
      ),
    },
    {
      header: "Current Value",
      key: "current-value",
      render: (item: PortfolioItem) => (
        <span className="text-[var(--color-text-muted)]">
          {currency(item.current_total_value)}
        </span>
      ),
    },
    {
      header: "Gain/Loss",
      key: "gain-loss",
      render: (item: PortfolioItem) => {
        const gain = Number(item.unrealized_gain_loss ?? 0);
        return (
          <span
            className={`font-bold ${gain >= 0 ? "semantic-gain" : "semantic-loss"}`}
          >
            {signedCurrency(item.unrealized_gain_loss)}
          </span>
        );
      },
    },
    {
      header: "Actions",
      key: "actions",
      render: (item: PortfolioItem) => (
        <button
          className="secondary-button"
          disabled={deleteMutation.isPending}
          onClick={() => setDeleteCandidate(item)}
          type="button"
        >
          Delete
        </button>
      ),
    },
  ];

  return (
    <section>
      {error ? (
        <div className="mb-5">
          <FormAlert>{error}</FormAlert>
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

      <Card className="mb-5">
        <form onSubmit={handleSubmit}>
          <CardHeader className="mb-4">
            <CardTitle>Add item</CardTitle>
          </CardHeader>
          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <TextField
              label="Set number"
              onChange={(event) => setSetNumber(event.target.value)}
              required
              value={setNumber}
            />
            <TextField
              label="Quantity"
              min="1"
              onChange={(event) => setQuantity(Number(event.target.value))}
              required
              type="number"
              value={quantity}
            />
            <TextField
              label="Purchase price"
              min="0"
              onChange={(event) => setPurchasePrice(event.target.value)}
              required
              step="0.01"
              type="number"
              value={purchasePrice}
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
            <TextField
              label="Acquired date"
              onChange={(event) => setAcquiredAt(event.target.value)}
              type="date"
              value={acquiredAt}
            />
            <TextField
              containerClassName="md:col-span-2 xl:col-span-1"
              label="Notes"
              onChange={(event) => setNotes(event.target.value)}
              value={notes}
            />
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
      </Card>

      <section className="page-card overflow-hidden p-0">
        <div className="border-b border-[var(--color-border-soft)] p-5">
          <h2 className="text-lg font-bold text-[var(--color-text)]">
            Holdings
          </h2>
        </div>
        <DataTable
          columns={columns}
          emptyMessage="Add a LEGO set holding to begin tracking value."
          getRowKey={(item) => item.id}
          isLoading={itemsQuery.isLoading}
          minWidth="920px"
          rows={items}
        />
      </section>
      <ConfirmationDialog
        confirmLabel="Delete"
        description={`Delete ${deleteCandidate?.set_number ?? "this portfolio item"} from your portfolio.`}
        isBusy={deleteMutation.isPending}
        isOpen={Boolean(deleteCandidate)}
        onCancel={() => setDeleteCandidate(null)}
        onConfirm={() => {
          if (deleteCandidate) {
            void deleteMutation.mutate(deleteCandidate.id).then(() => {
              setDeleteCandidate(null);
            });
          }
        }}
        title="Delete portfolio item"
      />
    </section>
  );
}
