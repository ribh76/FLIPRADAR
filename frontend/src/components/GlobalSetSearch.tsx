import { Search } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useServerQuery } from "../hooks/serverState";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { apiClient } from "../services/apiClient";
import {
  getRecentSetSearches,
  saveRecentSetSearch,
} from "../utils/navigationState";

export function GlobalSetSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [recentSearches, setRecentSearches] = useState(getRecentSetSearches);
  const trimmedQuery = query.trim();
  const debouncedQuery = useDebouncedValue(trimmedQuery);
  const resultsQuery = useServerQuery(
    ["global-set-search", debouncedQuery],
    useCallback(
      (signal: AbortSignal) => apiClient.sets.list(debouncedQuery, 6, signal),
      [debouncedQuery],
    ),
    { abortOnUnmount: true, enabled: debouncedQuery.length >= 2 },
  );
  const results = resultsQuery.data?.data ?? [];
  const isOpen = isFocused && trimmedQuery.length >= 2;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedQuery) return;
    const exactMatch = results.find(
      (set) => set.set_number.toLowerCase() === trimmedQuery.toLowerCase(),
    );
    navigate(
      exactMatch
        ? `/sets/${encodeURIComponent(exactMatch.set_number)}`
        : `/sets?query=${encodeURIComponent(trimmedQuery)}`,
    );
    saveRecentSetSearch(trimmedQuery);
    setRecentSearches(getRecentSetSearches());
    setIsFocused(false);
  }

  return (
    <div className="relative w-full sm:w-80" onBlur={() => setIsFocused(false)}>
      <form onSubmit={submit}>
        <label className="sr-only" htmlFor="global-set-search">
          Search sets
        </label>
        <div className="flex overflow-hidden rounded-[var(--radius-control)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-sm focus-within:border-[var(--color-accent)]">
          <Search
            aria-hidden="true"
            className="ml-3 shrink-0 self-center text-[var(--color-text-muted)]"
            size={16}
          />
          <input
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm font-semibold outline-none placeholder:text-[var(--color-text-muted)]"
            id="global-set-search"
            onChange={(event) => setQuery(event.target.value)}
            onFocus={() => setIsFocused(true)}
            placeholder="Search sets anywhere"
            value={query}
          />
        </div>
      </form>
      {isFocused && (isOpen || recentSearches.length) ? (
        <div className="absolute right-0 z-40 mt-2 w-full overflow-hidden rounded-[var(--radius-card)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-[var(--shadow-lifted)]">
          {!trimmedQuery ? (
            <>
              <p className="px-4 pt-3 text-xs font-bold uppercase text-[var(--color-text-muted)]">
                Recent searches
              </p>
              {recentSearches.map((recentQuery) => (
                <button
                  className="block w-full border-t border-[var(--color-border-soft)] px-4 py-3 text-left text-sm font-semibold hover:bg-[var(--color-surface-muted)]"
                  key={recentQuery}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    setQuery(recentQuery);
                    navigate(`/sets?query=${encodeURIComponent(recentQuery)}`);
                    setIsFocused(false);
                  }}
                  type="button"
                >
                  {recentQuery}
                </button>
              ))}
            </>
          ) : resultsQuery.isLoading ? (
            <p className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
              Searching catalog…
            </p>
          ) : results.length ? (
            results.map((set) => (
              <Link
                className="block border-b border-[var(--color-border-soft)] px-4 py-3 last:border-b-0 hover:bg-[var(--color-surface-muted)]"
                key={set.id}
                onMouseDown={(event) => {
                  event.preventDefault();
                  saveRecentSetSearch(set.set_number);
                }}
                onClick={() => setIsFocused(false)}
                to={`/sets/${encodeURIComponent(set.set_number)}`}
              >
                <strong className="block text-sm text-[var(--color-text)]">
                  {set.name}
                </strong>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {set.set_number} · {set.theme ?? "Theme unavailable"}
                </span>
              </Link>
            ))
          ) : (
            <p className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
              No matching sets. Press Enter to search the full catalog.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
