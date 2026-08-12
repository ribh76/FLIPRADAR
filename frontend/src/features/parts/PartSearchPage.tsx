import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  TextField,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import { PartSearchCard } from "./PartSearchCard";

const pageSize = 12;

function readYear(value: string | null): number | undefined {
  if (!value) return undefined;
  const year = Number(value);
  return Number.isInteger(year) ? year : undefined;
}

export function PartSearchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const query = searchParams.get("query")?.trim() ?? "";
  const offset = Math.max(0, Number(searchParams.get("offset")) || 0);
  const color = searchParams.get("color")?.trim() || undefined;
  const category = searchParams.get("category")?.trim() || undefined;
  const year = readYear(searchParams.get("year"));
  const [searchValue, setSearchValue] = useState(query);
  const [colorValue, setColorValue] = useState(color ?? "");
  const [categoryValue, setCategoryValue] = useState(category ?? "");
  const [yearValue, setYearValue] = useState(year?.toString() ?? "");
  const [validationMessage, setValidationMessage] = useState("");

  const loadSearch = useCallback(
    (signal: AbortSignal) =>
      apiClient.parts.search(
        query,
        { category, color, limit: pageSize, offset, year },
        signal,
      ),
    [category, color, offset, query, year],
  );
  const searchQuery = useServerQuery(
    ["part-search", query, color ?? "", category ?? "", year ?? 0, offset],
    loadSearch,
    { abortOnUnmount: true, enabled: Boolean(query) },
  );

  useEffect(() => {
    setSearchValue(query);
    setColorValue(color ?? "");
    setCategoryValue(category ?? "");
    setYearValue(year?.toString() ?? "");
  }, [category, color, query, year]);

  function navigateToSearch(nextOffset = 0, clearFilters = false) {
    const nextQuery = searchValue.trim();
    if (!nextQuery) {
      setValidationMessage("Enter a part number, name, or alternate name.");
      return;
    }
    const params = new URLSearchParams({ query: nextQuery });
    if (!clearFilters) {
      if (colorValue.trim()) params.set("color", colorValue.trim());
      if (categoryValue.trim()) params.set("category", categoryValue.trim());
      if (yearValue.trim()) params.set("year", yearValue.trim());
    }
    if (nextOffset) params.set("offset", nextOffset.toString());
    setValidationMessage("");
    navigate(`/parts?${params.toString()}`);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (yearValue && !/^(19[5-9]\d|20\d\d|2100)$/.test(yearValue)) {
      setValidationMessage("Enter a year from 1950 through 2100.");
      return;
    }
    navigateToSearch();
  }

  const results = searchQuery.data?.results ?? [];
  const pagination = searchQuery.data?.pagination;

  return (
    <section>
      <Card>
        <form
          className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_10rem_10rem_7rem_auto]"
          onSubmit={handleSubmit}
        >
          <TextField
            label="Part number or description"
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder="Try 3001, Brick 2 x 4, or 2x4 Brick"
            value={searchValue}
          />
          <TextField
            label="Color"
            onChange={(event) => setColorValue(event.target.value)}
            placeholder="Red"
            value={colorValue}
          />
          <TextField
            label="Category"
            onChange={(event) => setCategoryValue(event.target.value)}
            placeholder="Bricks"
            value={categoryValue}
          />
          <TextField
            label="Year"
            inputMode="numeric"
            onChange={(event) => setYearValue(event.target.value)}
            placeholder="1958"
            value={yearValue}
          />
          <button className="primary-button self-end" type="submit">
            Search parts
          </button>
        </form>
      </Card>

      <div className="mt-5 space-y-5">
        {validationMessage ? (
          <ErrorState
            message={validationMessage}
            title="Invalid search input"
          />
        ) : null}
        {searchQuery.isLoading ? (
          <LoadingState title="Searching part catalog..." />
        ) : null}
        {searchQuery.error ? (
          searchQuery.error.toLowerCase().includes("not found") ? (
            <PartEmptyState onClearFilters={() => navigateToSearch(0, true)} />
          ) : (
            <ErrorState
              message={searchQuery.error}
              onRetry={() => void searchQuery.refetch()}
              title="Part catalog lookup unavailable"
            />
          )
        ) : null}
        {searchQuery.data && results.length === 0 ? (
          <PartEmptyState onClearFilters={() => navigateToSearch(0, true)} />
        ) : null}
        {results.map((part) => (
          <PartSearchCard key={part.id} part={part} />
        ))}
        {pagination ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-[var(--color-text-muted)]">
              Showing {offset + 1}–{offset + results.length} matching parts
            </p>
            <div className="flex gap-2">
              <button
                className="secondary-button"
                disabled={offset === 0}
                onClick={() => navigateToSearch(Math.max(0, offset - pageSize))}
                type="button"
              >
                Previous
              </button>
              <button
                className="secondary-button"
                disabled={!pagination.has_more}
                onClick={() => navigateToSearch(offset + pageSize)}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function PartEmptyState({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <EmptyState
      message="Try the exact part number, remove filters, use a shorter description, or check an alternate part name."
      title="No matching parts"
    >
      <button
        className="secondary-button mt-3"
        onClick={onClearFilters}
        type="button"
      >
        Search without filters
      </button>
    </EmptyState>
  );
}
