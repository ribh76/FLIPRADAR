import type { FormEvent } from "react";
import { useCallback, useMemo, useState } from "react";
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
  Modal,
  SelectField,
  TextField,
} from "../../components/ui";
import type {
  Condition,
  PortfolioFilters,
  PortfolioItem,
  PortfolioItemCreate,
} from "../../types";
import { currency, signedCurrency } from "../../utils/format";

const portfolioKey = ["portfolio"];
const portfolioSummaryKey = ["portfolio-summary"];
const pageSize = 25;

type ItemFormProps = {
  initial?: PortfolioItem | null;
  isBusy: boolean;
  onCancel?: () => void;
  onSubmit: (payload: PortfolioItemCreate) => void;
};

function ItemForm({ initial, isBusy, onCancel, onSubmit }: ItemFormProps) {
  const [setNumber, setSetNumber] = useState(initial?.set_number ?? "");
  const [quantity, setQuantity] = useState(initial?.quantity ?? 1);
  const [purchasePrice, setPurchasePrice] = useState(
    String(initial?.purchase_price ?? ""),
  );
  const [condition, setCondition] = useState<Condition>(
    (initial?.condition as Condition) ?? "new",
  );
  const [purchaseDate, setPurchaseDate] = useState(
    initial?.purchase_date?.slice(0, 10) ?? "",
  );
  const [itemCurrency, setItemCurrency] = useState(initial?.currency ?? "USD");
  const [notes, setNotes] = useState(initial?.notes ?? "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({
      set_number: setNumber,
      quantity,
      purchase_price: Number(purchasePrice),
      condition,
      purchase_date: purchaseDate
        ? new Date(`${purchaseDate}T00:00:00`).toISOString()
        : null,
      currency: itemCurrency.toUpperCase(),
      notes: notes || null,
    });
  }

  return (
    <form onSubmit={submit}>
      <div className="grid gap-4 md:grid-cols-3">
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
          onChange={(event) => setCondition(event.target.value as Condition)}
          value={condition}
        >
          <option value="new">New</option>
          <option value="used">Used</option>
          <option value="sealed">Sealed</option>
          <option value="unknown">Unknown</option>
        </SelectField>
        <TextField
          label="Purchase date"
          onChange={(event) => setPurchaseDate(event.target.value)}
          type="date"
          value={purchaseDate}
        />
        <TextField
          label="Currency"
          maxLength={3}
          onChange={(event) =>
            setItemCurrency(event.target.value.toUpperCase())
          }
          pattern="[A-Z]{3}"
          required
          value={itemCurrency}
        />
        <TextField
          containerClassName="md:col-span-3"
          label="Notes"
          onChange={(event) => setNotes(event.target.value)}
          value={notes}
        />
      </div>
      <div className="mt-4 flex flex-wrap justify-end gap-3">
        {onCancel ? (
          <button className="secondary-button" onClick={onCancel} type="button">
            Cancel
          </button>
        ) : null}
        <button className="primary-button" disabled={isBusy} type="submit">
          {isBusy ? "Saving..." : initial ? "Save changes" : "Add set"}
        </button>
      </div>
    </form>
  );
}

export function PortfolioPage() {
  const [filters, setFilters] = useState<PortfolioFilters>({
    order: "purchase_date_desc",
    limit: pageSize,
    offset: 0,
  });
  const [editCandidate, setEditCandidate] = useState<PortfolioItem | null>(
    null,
  );
  const [deleteCandidate, setDeleteCandidate] = useState<PortfolioItem | null>(
    null,
  );
  const loadPortfolio = useCallback(
    () => apiClient.portfolio.list(filters),
    [filters],
  );
  const loadSummary = useCallback(() => apiClient.portfolio.summary(), []);
  const itemsQuery = useServerQuery(
    [...portfolioKey, JSON.stringify(filters)],
    loadPortfolio,
  );
  const summaryQuery = useServerQuery(portfolioSummaryKey, loadSummary);
  const refreshPortfolio = useCallback(async () => {
    invalidateServerState(portfolioSummaryKey);
    await Promise.all([itemsQuery.refetch(), summaryQuery.refetch()]);
  }, [itemsQuery, summaryQuery]);
  const addMutation = useServerMutation(apiClient.portfolio.addItem, {
    onSuccess: refreshPortfolio,
  });
  const updateMutation = useServerMutation(
    ({ id, payload }: { id: string; payload: PortfolioItemCreate }) =>
      apiClient.portfolio.updateItem(id, payload),
    { onSuccess: refreshPortfolio },
  );
  const deleteMutation = useServerMutation(apiClient.portfolio.deleteItem, {
    onSuccess: refreshPortfolio,
  });
  const items = itemsQuery.data?.data ?? [];
  const pagination = itemsQuery.data?.pagination;
  const error =
    itemsQuery.error ||
    summaryQuery.error ||
    addMutation.error ||
    updateMutation.error ||
    deleteMutation.error;
  const filterValues = useMemo(
    () => ({
      ...filters,
      condition: filters.condition ?? "",
      theme: filters.theme ?? "",
      year: filters.year ?? "",
      performance: filters.performance ?? "",
    }),
    [filters],
  );

  const columns = [
    {
      header: "Set",
      key: "set",
      render: (item: PortfolioItem) => (
        <div>
          <strong className="text-[var(--color-text)]">
            {item.set_number}
          </strong>
          <div className="text-xs text-[var(--color-text-muted)]">
            {item.set_name ?? "--"}
          </div>
        </div>
      ),
    },
    {
      header: "Condition",
      key: "condition",
      render: (item: PortfolioItem) => (
        <span className="capitalize">{item.condition}</span>
      ),
    },
    {
      header: "Qty",
      key: "quantity",
      render: (item: PortfolioItem) => item.quantity,
    },
    {
      header: "Purchase",
      key: "purchase",
      render: (item: PortfolioItem) => (
        <div>
          {currency(item.purchase_price, item.currency)}
          <div className="text-xs text-[var(--color-text-muted)]">
            {item.purchase_date?.slice(0, 10) ?? "No date"}
          </div>
        </div>
      ),
    },
    {
      header: "Value",
      key: "value",
      render: (item: PortfolioItem) =>
        currency(item.current_total_value, item.currency),
    },
    {
      header: "Gain/Loss",
      key: "gain",
      render: (item: PortfolioItem) => (
        <span
          className={
            Number(item.unrealized_gain_loss ?? 0) >= 0
              ? "semantic-gain font-bold"
              : "semantic-loss font-bold"
          }
        >
          {signedCurrency(item.unrealized_gain_loss)}
        </span>
      ),
    },
    {
      header: "Actions",
      key: "actions",
      render: (item: PortfolioItem) => (
        <div className="flex gap-2">
          <button
            className="secondary-button"
            onClick={() => setEditCandidate(item)}
            type="button"
          >
            Edit
          </button>
          <button
            className="secondary-button"
            onClick={() => setDeleteCandidate(item)}
            type="button"
          >
            Delete
          </button>
        </div>
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
          label="Total Quantity"
          tone="watch"
          value={String(summaryQuery.data?.total_quantity ?? 0)}
        />
      </div>
      <Card className="mb-5">
        <CardHeader className="mb-4">
          <CardTitle>Add set</CardTitle>
        </CardHeader>
        <ItemForm
          isBusy={addMutation.isPending}
          onSubmit={(payload) => void addMutation.mutate(payload)}
        />
      </Card>
      <section className="page-card overflow-hidden p-0">
        <div className="border-b border-[var(--color-border-soft)] p-5">
          <h2 className="text-lg font-bold text-[var(--color-text)]">
            Holdings
          </h2>
          <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            <TextField
              label="Theme"
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  theme: event.target.value || undefined,
                  offset: 0,
                }))
              }
              value={filterValues.theme}
            />
            <TextField
              label="Release year"
              min="1949"
              max="2100"
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  year: event.target.value
                    ? Number(event.target.value)
                    : undefined,
                  offset: 0,
                }))
              }
              type="number"
              value={filterValues.year}
            />
            <SelectField
              label="Condition"
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  condition: (event.target.value as Condition) || undefined,
                  offset: 0,
                }))
              }
              value={filterValues.condition}
            >
              <option value="">All conditions</option>
              <option value="new">New</option>
              <option value="used">Used</option>
              <option value="sealed">Sealed</option>
              <option value="unknown">Unknown</option>
            </SelectField>
            <SelectField
              label="Performance"
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  performance:
                    (event.target.value as PortfolioFilters["performance"]) ||
                    undefined,
                  offset: 0,
                }))
              }
              value={filterValues.performance}
            >
              <option value="">All performance</option>
              <option value="gain">Gain</option>
              <option value="loss">Loss</option>
              <option value="unvalued">Unvalued</option>
            </SelectField>
            <SelectField
              label="Sort"
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  order: event.target.value,
                  offset: 0,
                }))
              }
              value={filters.order}
            >
              <option value="purchase_date_desc">Purchase date (newest)</option>
              <option value="purchase_date_asc">Purchase date (oldest)</option>
              <option value="value_desc">Value (high to low)</option>
              <option value="value_asc">Value (low to high)</option>
              <option value="gain_desc">Gain (high to low)</option>
              <option value="gain_asc">Gain (low to high)</option>
              <option value="theme_asc">Theme (A–Z)</option>
              <option value="theme_desc">Theme (Z–A)</option>
            </SelectField>
          </div>
        </div>
        <DataTable
          columns={columns}
          emptyMessage="Add a LEGO set holding to begin tracking value."
          getRowKey={(item) => item.id}
          isLoading={itemsQuery.isLoading}
          minWidth="980px"
          rows={items}
        />
        <div className="flex items-center justify-between border-t border-[var(--color-border-soft)] p-4 text-sm text-[var(--color-text-muted)]">
          <span>{pagination?.count ?? 0} shown</span>
          <div className="flex gap-2">
            <button
              className="secondary-button"
              disabled={!filters.offset}
              onClick={() =>
                setFilters((value) => ({
                  ...value,
                  offset: Math.max(0, (value.offset ?? 0) - pageSize),
                }))
              }
              type="button"
            >
              Previous
            </button>
            <button
              className="secondary-button"
              disabled={!pagination?.has_more}
              onClick={() =>
                setFilters((value) => ({
                  ...value,
                  offset: (value.offset ?? 0) + pageSize,
                }))
              }
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      </section>
      <Modal
        isOpen={Boolean(editCandidate)}
        onClose={() => setEditCandidate(null)}
        title="Edit portfolio set"
      >
        {editCandidate ? (
          <ItemForm
            initial={editCandidate}
            isBusy={updateMutation.isPending}
            onCancel={() => setEditCandidate(null)}
            onSubmit={(payload) =>
              void updateMutation
                .mutate({ id: editCandidate.id, payload })
                .then(() => setEditCandidate(null))
            }
          />
        ) : null}
      </Modal>
      <ConfirmationDialog
        confirmLabel="Delete"
        description={`Delete ${deleteCandidate?.set_number ?? "this portfolio item"} from your portfolio?`}
        isBusy={deleteMutation.isPending}
        isOpen={Boolean(deleteCandidate)}
        onCancel={() => setDeleteCandidate(null)}
        onConfirm={() => {
          if (deleteCandidate)
            void deleteMutation
              .mutate(deleteCandidate.id)
              .then(() => setDeleteCandidate(null));
        }}
        title="Delete portfolio item"
      />
    </section>
  );
}
