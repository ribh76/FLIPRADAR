import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiClient } from "../../services/apiClient";
import { useServerQuery } from "../../hooks/serverState";
import {
  Card,
  ErrorState,
  LoadingState,
  MetricCard,
  TextField,
} from "../../components/ui";
import type { LegoSet, SetDetail } from "../../types";
import { currency, numberValue } from "../../utils/format";
import { SetCatalogCard } from "./SetCatalogCard";

function catalogFallback(detail: SetDetail): LegoSet {
  return {
    id: detail.set_number,
    set_number: detail.set_number,
    name: detail.name,
    theme: detail.theme,
    subtheme: detail.subtheme,
    release_year: detail.release_year,
    retirement_year: detail.retirement_year,
    piece_count: detail.piece_count,
    minifig_count: detail.minifig_count,
    msrp: null,
    original_currency: null,
    region: null,
    image_urls: null,
    source_name: null,
    source_url: null,
    data_quality_flag: false,
    completeness_flag: false,
    created_at: "",
    updated_at: detail.latest_snapshot?.retrieval_time ?? "",
  };
}

export function SetDetailPage() {
  const { setNumber } = useParams();
  const navigate = useNavigate();
  const [searchValue, setSearchValue] = useState(setNumber ?? "");
  const loadDetail = useCallback(
    () => apiClient.sets.detail(setNumber ?? ""),
    [setNumber],
  );
  const detailQuery = useServerQuery(
    ["set-detail", setNumber ?? ""],
    loadDetail,
    {
      enabled: Boolean(setNumber),
    },
  );
  const loadCatalog = useCallback(
    () => apiClient.sets.search(setNumber ?? ""),
    [setNumber],
  );
  const catalogQuery = useServerQuery(
    ["set-catalog-detail", setNumber ?? ""],
    loadCatalog,
    { enabled: Boolean(setNumber) },
  );
  const detail = detailQuery.data;
  const hasMarketData = detail?.valuation_status === "available";

  useEffect(() => {
    setSearchValue(setNumber ?? "");
  }, [setNumber]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextSetNumber = searchValue.trim();
    if (nextSetNumber) {
      navigate(`/sets?query=${encodeURIComponent(nextSetNumber)}`);
    }
  }

  return (
    <section>
      <Card className="mb-5">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={handleSubmit}
        >
          <div className="flex-1">
            <TextField
              label="Set number"
              onChange={(event) => setSearchValue(event.target.value)}
              placeholder="Enter set number"
              value={searchValue}
            />
          </div>
          <button className="primary-button self-end" type="submit">
            Search
          </button>
        </form>
      </Card>

      {detailQuery.error ? (
        <div className="mb-5">
          <ErrorState
            message={detailQuery.error}
            onRetry={() => void detailQuery.refetch()}
            title="Set detail unavailable"
          />
        </div>
      ) : null}
      {detailQuery.isLoading ? (
        <div className="mb-5">
          <LoadingState title="Loading set detail..." />
        </div>
      ) : null}

      {catalogQuery.error && detail ? (
        <div className="mb-5">
          <ErrorState
            message={catalogQuery.error}
            onRetry={() => void catalogQuery.refetch()}
            title="Catalog metadata unavailable"
          />
        </div>
      ) : null}

      {detail ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
          <section>
            <SetCatalogCard
              set={
                catalogQuery.data?.results.find(
                  (set) => set.set_number === detail.set_number,
                ) ?? catalogFallback(detail)
              }
            />
          </section>

          <aside className="page-card">
            <p className="metric-label">Valuation status</p>
            <div
              className={`mt-3 inline-flex rounded-md border px-3 py-2 text-sm font-bold ${
                hasMarketData
                  ? "border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] text-[var(--color-gain)]"
                  : "border-[var(--color-accent-warm)] bg-[rgba(235,136,30,0.14)] text-[var(--color-accent-warm)]"
              }`}
            >
              {detail.valuation_status}
            </div>
            {!hasMarketData ? (
              <div className="mt-5 rounded-[var(--radius-card)] border border-[var(--color-accent-warm)] bg-[rgba(235,136,30,0.14)] p-4 text-sm font-semibold leading-6 text-[var(--color-accent-warm)]">
                Set found, but no market valuation is available yet.
              </div>
            ) : null}
            {import.meta.env.DEV ? (
              <button className="secondary-button mt-5 w-full" type="button">
                Refresh Market Data
              </button>
            ) : null}
          </aside>

          <section className="page-card lg:col-span-2">
            <h2 className="text-lg font-bold text-[var(--color-text)]">
              Latest market snapshot
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <MetricCard
                label="Fair Value"
                tone="hold"
                value={currency(detail.fair_value)}
              />
              <MetricCard
                label="Market Low"
                value={currency(detail.market_low)}
              />
              <MetricCard
                label="Market High"
                value={currency(detail.market_high)}
              />
              <MetricCard
                label="Listing Count"
                value={numberValue(detail.listing_count)}
              />
              <MetricCard
                label="Confidence"
                tone="watch"
                value={detail.confidence?.toUpperCase() ?? "--"}
              />
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
