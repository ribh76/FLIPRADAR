import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  SelectField,
  TextField,
} from "../../components/ui";
import { useServerQuery } from "../../hooks/serverState";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { apiClient } from "../../services/apiClient";
import { SetCatalogCard } from "./SetCatalogCard";
import { saveRecentSetSearch } from "../../utils/navigationState";

export function SetsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const submittedQuery = searchParams.get("query")?.trim() ?? "";
  const [searchValue, setSearchValue] = useState(submittedQuery);
  const [provider, setProvider] = useState("bricklink");
  const [validationMessage, setValidationMessage] = useState("");
  const debouncedSearchValue = useDebouncedValue(searchValue.trim());
  const loadSuggestions = useCallback(
    (signal: AbortSignal) =>
      apiClient.sets.list(debouncedSearchValue, 8, signal),
    [debouncedSearchValue],
  );
  const suggestionsQuery = useServerQuery(
    ["set-suggestions", debouncedSearchValue],
    loadSuggestions,
    { abortOnUnmount: true, enabled: debouncedSearchValue.length >= 2 },
  );
  const loadSearch = useCallback(
    (signal: AbortSignal) =>
      apiClient.sets.search(submittedQuery, provider, 25, signal),
    [provider, submittedQuery],
  );
  const searchQuery = useServerQuery(
    ["set-search", submittedQuery, provider],
    loadSearch,
    { abortOnUnmount: true, enabled: Boolean(submittedQuery) },
  );

  useEffect(() => {
    setSearchValue(submittedQuery);
  }, [submittedQuery]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchValue.trim();
    if (!query) {
      setValidationMessage("Enter a LEGO set number or a known set name.");
      return;
    }
    if (!/^[a-z0-9\s-]+$/i.test(query)) {
      setValidationMessage("Use letters, numbers, spaces, and hyphens only.");
      return;
    }
    setValidationMessage("");
    saveRecentSetSearch(query);
    navigate(`/sets?query=${encodeURIComponent(query)}`);
  }

  return (
    <section>
      <Card>
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={handleSubmit}
        >
          <div className="flex-1">
            <TextField
              label="Set number or name"
              list="known-lego-sets"
              onChange={(event) => setSearchValue(event.target.value)}
              placeholder="Try 75192, 420, or Millennium Falcon"
              value={searchValue}
            />
            <datalist id="known-lego-sets">
              {suggestionsQuery.data?.data.flatMap((set) => [
                <option
                  key={`${set.id}-number`}
                  label={set.name}
                  value={set.set_number}
                />,
                <option
                  key={`${set.id}-name`}
                  label={set.set_number}
                  value={set.name}
                />,
              ])}
            </datalist>
          </div>
          <SelectField
            containerClassName="sm:w-44"
            label="Provider"
            onChange={(event) => setProvider(event.target.value)}
            value={provider}
          >
            <option value="bricklink">BrickLink</option>
          </SelectField>
          <button className="primary-button self-end" type="submit">
            Search
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
          <LoadingState title="Searching set catalog..." />
        ) : null}
        {searchQuery.error ? (
          searchQuery.error.toLowerCase().includes("not found") ? (
            <EmptyState
              message="Try a different set number, partial number, or known set name."
              title="No matching sets"
            />
          ) : (
            <ErrorState
              message={searchQuery.error}
              onRetry={() => void searchQuery.refetch()}
              title="Provider lookup unavailable"
            />
          )
        ) : null}
        {searchQuery.data?.results.length === 0 ? (
          <EmptyState title="No matching sets" />
        ) : null}
        {searchQuery.data?.results.map((set) => (
          <SetCatalogCard
            key={set.id}
            onViewDetail={(setNumber) =>
              navigate(`/sets/${encodeURIComponent(setNumber)}`)
            }
            set={set}
          />
        ))}
      </div>
    </section>
  );
}
