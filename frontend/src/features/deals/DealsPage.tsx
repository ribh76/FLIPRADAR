import { RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageState,
  SelectField,
  TextField,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient, getApiError } from "../../services/apiClient";
import type { DealFilters, DealsResponse, SavedSearch } from "../../types";
import { DealCard } from "./DealCard";
import { getSavedDealFilters, saveDealFilters } from "../../utils/navigationState";

const numberFilters = new Set([
  "min_budget",
  "max_budget",
  "min_release_year",
  "max_release_year",
  "min_age_years",
  "max_age_years",
  "min_discount",
  "min_confidence",
  "max_shipping",
]);

const filterLabels: Record<string, string> = {
  set_number: "Set number",
  min_budget: "Min budget",
  max_budget: "Max budget",
  theme: "Theme",
  subtheme: "Subtheme",
  min_release_year: "Released after",
  max_release_year: "Released before",
  min_age_years: "Min age",
  max_age_years: "Max age",
  condition: "Condition",
  retirement_status: "Retirement",
  marketplace: "Marketplace",
  min_discount: "Min discount",
  min_confidence: "Min confidence",
  max_shipping: "Max shipping",
  order: "Sort",
};

function parseFilters(searchParams: URLSearchParams): DealFilters {
  return Object.fromEntries(
    [...searchParams.entries()].map(([key, value]) => [
      key,
      numberFilters.has(key) ? Number(value) : value,
    ]),
  ) as DealFilters;
}

export function DealsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const restoringFilters = useRef(false);
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const filterKey = searchParams.toString();
  useEffect(() => {
    if (filterKey || restoringFilters.current) return;
    const savedFilters = getSavedDealFilters();
    if (!savedFilters) return;
    restoringFilters.current = true;
    setSearchParams(new URLSearchParams(savedFilters), { replace: true });
  }, [filterKey, setSearchParams]);
  useEffect(() => {
    if (restoringFilters.current) {
      restoringFilters.current = false;
      return;
    }
    saveDealFilters(filterKey);
  }, [filterKey]);
  const loadDeals = useCallback(() => apiClient.deals.list(filters), [filters]);
  const dealsQuery = useServerQuery<DealsResponse>(
    ["deals", filterKey],
    loadDeals,
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");
  const [savedSearchName, setSavedSearchName] = useState("");
  const [selectedSearchId, setSelectedSearchId] = useState("");
  const savedSearchQuery = useServerQuery<SavedSearch[]>(
    ["saved-searches"],
    useCallback(() => apiClient.savedSearches.list(), []),
  );

  function updateFilter(name: string, value: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      return next;
    });
  }

  async function saveCurrentSearch() {
    if (!savedSearchName.trim()) return;
    const saved = await apiClient.savedSearches.create({
      name: savedSearchName,
      filter_config: filters,
    });
    savedSearchQuery.setData([saved, ...(savedSearchQuery.data ?? [])]);
    setSelectedSearchId(saved.id);
    setSavedSearchName("");
  }

  async function selectSavedSearch(id: string) {
    setSelectedSearchId(id);
    const saved = savedSearchQuery.data?.find((search) => search.id === id);
    if (!saved) return;
    setSearchParams(
      Object.fromEntries(
        Object.entries(saved.filter_config).map(([key, value]) => [
          key,
          String(value),
        ]),
      ),
    );
    const run = await apiClient.savedSearches.recordRun(id);
    savedSearchQuery.setData(
      (savedSearchQuery.data ?? []).map((search) =>
        search.id === id ? run : search,
      ),
    );
  }

  async function updateSelectedSearch() {
    if (!selectedSearchId || !savedSearchName.trim()) return;
    const saved = await apiClient.savedSearches.update(selectedSearchId, {
      name: savedSearchName,
      filter_config: filters,
    });
    savedSearchQuery.setData(
      (savedSearchQuery.data ?? []).map((search) =>
        search.id === saved.id ? saved : search,
      ),
    );
  }

  async function duplicateSelectedSearch() {
    if (!selectedSearchId) return;
    const saved = await apiClient.savedSearches.duplicate(selectedSearchId);
    savedSearchQuery.setData([saved, ...(savedSearchQuery.data ?? [])]);
    setSelectedSearchId(saved.id);
  }

  async function deleteSelectedSearch() {
    if (!selectedSearchId) return;
    await apiClient.savedSearches.remove(selectedSearchId);
    savedSearchQuery.setData(
      (savedSearchQuery.data ?? []).filter(
        (search) => search.id !== selectedSearchId,
      ),
    );
    setSelectedSearchId("");
  }

  async function refreshDeals() {
    setIsRefreshing(true);
    setRefreshError("");
    try {
      const refreshed = await apiClient.deals.list({
        ...filters,
        refresh: true,
      });
      dealsQuery.setData(refreshed);
    } catch (error) {
      setRefreshError(getApiError(error));
    } finally {
      setIsRefreshing(false);
    }
  }

  const refresh = dealsQuery.data?.refresh;
  const hasCards = Boolean(dealsQuery.data?.data.length);
  const activeFilters = [...searchParams.entries()];

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[var(--color-text-muted)]">
            Personalized catalog discovery
          </p>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Active, matched listings ranked by your price, quality, and catalog
            preferences.
          </p>
        </div>
        <button
          className="primary-button"
          disabled={isRefreshing}
          onClick={() => void refreshDeals()}
          type="button"
        >
          <RefreshCw className={isRefreshing ? "animate-spin" : ""} size={16} />
          {isRefreshing ? "Refreshing..." : "Refresh deals"}
        </button>
      </div>

      <Card>
        <div className="mb-5 grid gap-3 border-b border-[var(--color-border-soft)] pb-5 md:grid-cols-[1fr_1fr_auto_auto_auto]">
          <SelectField
            label="Saved searches"
            onChange={(event) => void selectSavedSearch(event.target.value)}
            value={selectedSearchId}
          >
            <option value="">Select a saved search</option>
            {savedSearchQuery.data?.map((search) => (
              <option key={search.id} value={search.id}>
                {search.name} ·{" "}
                {search.last_run_at
                  ? new Date(search.last_run_at).toLocaleDateString()
                  : "never run"}{" "}
                · {search.result_count} results
              </option>
            ))}
          </SelectField>
          <TextField
            label="Search name"
            onChange={(event) => setSavedSearchName(event.target.value)}
            placeholder="e.g. Retired UCS under $500"
            value={savedSearchName}
          />
          <button
            className="secondary-button self-end"
            onClick={() => void saveCurrentSearch()}
            type="button"
          >
            Save current
          </button>
          <button
            className="secondary-button self-end"
            disabled={!selectedSearchId}
            onClick={() => void updateSelectedSearch()}
            type="button"
          >
            Update
          </button>
          <button
            className="secondary-button self-end"
            disabled={!selectedSearchId}
            onClick={() => void duplicateSelectedSearch()}
            type="button"
          >
            Duplicate
          </button>
          {selectedSearchId ? (
            <button
              className="secondary-button self-end"
              onClick={() => void deleteSelectedSearch()}
              type="button"
            >
              Delete
            </button>
          ) : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <TextField
            label="Minimum budget"
            min="0"
            onChange={(event) => updateFilter("min_budget", event.target.value)}
            step="0.01"
            type="number"
            value={searchParams.get("min_budget") ?? ""}
          />
          <TextField
            label="Maximum budget"
            min="0"
            onChange={(event) => updateFilter("max_budget", event.target.value)}
            step="0.01"
            type="number"
            value={searchParams.get("max_budget") ?? ""}
          />
          <TextField
            label="Theme"
            onChange={(event) => updateFilter("theme", event.target.value)}
            value={searchParams.get("theme") ?? ""}
          />
          <TextField
            label="Subtheme"
            onChange={(event) => updateFilter("subtheme", event.target.value)}
            value={searchParams.get("subtheme") ?? ""}
          />
          <TextField
            label="Release year from"
            min="1949"
            max="2100"
            onChange={(event) =>
              updateFilter("min_release_year", event.target.value)
            }
            type="number"
            value={searchParams.get("min_release_year") ?? ""}
          />
          <TextField
            label="Release year to"
            min="1949"
            max="2100"
            onChange={(event) =>
              updateFilter("max_release_year", event.target.value)
            }
            type="number"
            value={searchParams.get("max_release_year") ?? ""}
          />
          <TextField
            label="Minimum age (years)"
            min="0"
            onChange={(event) =>
              updateFilter("min_age_years", event.target.value)
            }
            type="number"
            value={searchParams.get("min_age_years") ?? ""}
          />
          <TextField
            label="Maximum age (years)"
            min="0"
            onChange={(event) =>
              updateFilter("max_age_years", event.target.value)
            }
            type="number"
            value={searchParams.get("max_age_years") ?? ""}
          />
          <SelectField
            label="Condition"
            onChange={(event) => updateFilter("condition", event.target.value)}
            value={searchParams.get("condition") ?? ""}
          >
            <option value="">Any condition</option>
            <option value="new">New</option>
            <option value="sealed">Sealed</option>
            <option value="used">Used</option>
            <option value="unknown">Unknown</option>
          </SelectField>
          <SelectField
            label="Retirement"
            onChange={(event) =>
              updateFilter("retirement_status", event.target.value)
            }
            value={searchParams.get("retirement_status") ?? ""}
          >
            <option value="">Any status</option>
            <option value="retired">Retired</option>
            <option value="active">Not retired</option>
          </SelectField>
          <SelectField
            label="Marketplace"
            onChange={(event) =>
              updateFilter("marketplace", event.target.value)
            }
            value={searchParams.get("marketplace") ?? ""}
          >
            <option value="">All marketplaces</option>
            <option value="ebay">eBay</option>
            <option value="bricklink">BrickLink</option>
          </SelectField>
          <SelectField
            label="Sort"
            onChange={(event) => updateFilter("order", event.target.value)}
            value={searchParams.get("order") ?? "score_desc"}
          >
            <option value="score_desc">Highest score</option>
            <option value="discount_desc">Largest discount</option>
            <option value="total_price_asc">Lowest total price</option>
            <option value="total_price_desc">Highest total price</option>
            <option value="confidence_desc">Highest confidence</option>
          </SelectField>
          <TextField
            label="Minimum discount (%)"
            min="0"
            max="100"
            onChange={(event) =>
              updateFilter("min_discount", event.target.value)
            }
            type="number"
            value={searchParams.get("min_discount") ?? ""}
          />
          <TextField
            label="Minimum confidence"
            min="0"
            max="100"
            onChange={(event) =>
              updateFilter("min_confidence", event.target.value)
            }
            type="number"
            value={searchParams.get("min_confidence") ?? ""}
          />
          <TextField
            label="Maximum shipping"
            min="0"
            onChange={(event) =>
              updateFilter("max_shipping", event.target.value)
            }
            step="0.01"
            type="number"
            value={searchParams.get("max_shipping") ?? ""}
          />
        </div>
      </Card>

      {activeFilters.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="metric-label">Active filters</span>
          {activeFilters.map(([name, value]) => (
            <button
              className="secondary-button h-8 gap-1 px-2"
              key={name}
              onClick={() => updateFilter(name, "")}
              type="button"
            >
              {filterLabels[name] ?? name}: {value}
              <X aria-hidden="true" size={14} />
            </button>
          ))}
          <button
            className="text-sm font-bold text-[var(--color-accent)] hover:underline"
            onClick={() => {
              saveDealFilters("");
              setSearchParams({});
            }}
            type="button"
          >
            Clear all
          </button>
        </div>
      ) : null}

      {refresh?.throttled ? (
        <PageState title="Refresh is cooling down" tone="warning">
          Try again in {refresh.retry_after_seconds ?? 60} seconds. Showing the
          most recent saved results.
        </PageState>
      ) : null}
      {refresh?.provider_errors.length ? (
        <PageState title="Partial marketplace results" tone="warning">
          {refresh.provider_errors.join(" ")} Existing deal cards remain
          available while the next refresh retries the provider.
        </PageState>
      ) : null}
      {refreshError ? (
        <ErrorState
          message={
            hasCards
              ? `${refreshError} Showing previous deal results.`
              : refreshError
          }
          onRetry={() => void refreshDeals()}
          title="Refresh unavailable"
        />
      ) : null}
      {dealsQuery.isLoading ? (
        <LoadingState title="Finding active deals..." />
      ) : null}
      {dealsQuery.error && !hasCards ? (
        <ErrorState
          message={dealsQuery.error}
          onRetry={() => void dealsQuery.refetch()}
          title="Deal finder unavailable"
        />
      ) : null}
      {!dealsQuery.isLoading && !dealsQuery.error && !hasCards ? (
        <EmptyState
          message="No eligible listings match these filters."
          title="No deals right now"
        />
      ) : null}
      {dealsQuery.data?.data.map((deal) => (
        <DealCard deal={deal} key={deal.listing_id} />
      ))}
    </section>
  );
}
