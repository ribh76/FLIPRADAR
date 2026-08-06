import type { FormEvent } from "react";
import { useState } from "react";
import { apiClient, getApiError } from "../../services/apiClient";
import {
  Card,
  CardHeader,
  CardTitle,
  FormAlert,
  MetricCard,
  SelectField,
  StatusBadge,
  TextField,
} from "../../components/ui";
import type {
  Condition,
  Listing,
  ListingAnalysis,
  ManualListingEntry,
} from "../../types";
import { currency, numberValue, percent } from "../../utils/format";

const stages = ["Validating URL", "Retrieving listing", "Scoring deal"];

function detectedMarketplace(url: string) {
  const host = url.toLowerCase();
  if (host.includes("ebay")) return "eBay";
  if (host.includes("bricklink")) return "BrickLink";
  return "Supported marketplace detected after validation";
}

export function ListingEvaluatorPage() {
  const [url, setUrl] = useState("");
  const [setNumber, setSetNumber] = useState("");
  const [listing, setListing] = useState<Listing | null>(null);
  const [analysis, setAnalysis] = useState<ListingAnalysis | null>(null);
  const [stage, setStage] = useState(-1);
  const [error, setError] = useState("");
  const [portfolioMessage, setPortfolioMessage] = useState("");
  const [watchlistMessage, setWatchlistMessage] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState<ManualListingEntry>({
    title: "",
    price: 0,
    shipping_price: 0,
    currency: "USD",
    condition: "unknown",
  });

  const busy = stage >= 0;
  async function evaluate(manualListing?: ManualListingEntry) {
    setError("");
    setPortfolioMessage("");
    setAnalysis(null);
    setListing(null);
    setStage(0);
    try {
      setStage(1);
      const saved = await apiClient.listings.evaluate({
        set_number: setNumber,
        url,
        ...(manualListing ? { manual_listing: manualListing } : {}),
      });
      setListing(saved);
      setStage(2);
      setAnalysis(await apiClient.listings.analyze(saved.id));
      setManualOpen(false);
    } catch (requestError) {
      setError(getApiError(requestError));
      setManualOpen(true);
    } finally {
      setStage(-1);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void evaluate();
  }
  function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void evaluate(manual);
  }
  async function addToPortfolio() {
    if (!listing) return;
    setPortfolioMessage("");
    try {
      await apiClient.portfolio.addItem({
        set_number: setNumber,
        quantity: 1,
        purchase_price: Number(listing.total_price),
        condition: listing.condition,
        purchase_date: new Date().toISOString(),
        currency: listing.currency,
        notes: `Imported from ${listing.url}`,
      });
      setPortfolioMessage("Added to your purchase portfolio.");
    } catch (requestError) {
      setPortfolioMessage(getApiError(requestError));
    }
  }
  async function addToWatchlist() {
    if (!listing) return;
    setWatchlistMessage("");
    try {
      await apiClient.watchlist.addListing(listing.id);
      setWatchlistMessage("Saved to watchlist.");
    } catch (requestError) {
      setWatchlistMessage(getApiError(requestError));
    }
  }

  return (
    <section className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[420px_1fr]">
        <Card>
          <form className="space-y-4" onSubmit={submit}>
            <CardHeader>
              <CardTitle>Listing URL</CardTitle>
            </CardHeader>
            <TextField
              label="Listing URL"
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.ebay.com/itm/..."
              required
              value={url}
            />
            <p className="text-xs text-[var(--color-text-muted)]">
              {detectedMarketplace(url)}
            </p>
            <TextField
              label="Set number"
              onChange={(event) => setSetNumber(event.target.value)}
              placeholder="75192"
              required
              value={setNumber}
            />
            {busy ? (
              <div aria-label="Retrieval progress" className="space-y-2">
                <div className="h-2 overflow-hidden rounded bg-[var(--color-surface-muted)]">
                  <div
                    className="h-full bg-brand-accent transition-all"
                    style={{ width: `${((stage + 1) / stages.length) * 100}%` }}
                  />
                </div>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {stages[stage]}
                </p>
              </div>
            ) : null}
            <FormAlert>{error}</FormAlert>
            <button
              className="primary-button w-full"
              disabled={busy}
              type="submit"
            >
              {busy ? "Retrieving..." : "Evaluate listing"}
            </button>
          </form>
        </Card>
        <section className="space-y-5">
          {analysis && listing ? (
            <Results
              listing={listing}
              analysis={analysis}
              onPortfolio={() => void addToPortfolio()}
              onWatchlist={() => void addToWatchlist()}
              portfolioMessage={portfolioMessage}
              watchlistMessage={watchlistMessage}
            />
          ) : (
            <div className="page-card text-sm text-[var(--color-text-muted)]">
              Enter a supported eBay or BrickLink URL to inspect normalized
              details, fair value, and risk.
            </div>
          )}
        </section>
      </div>
      {manualOpen ? (
        <Card>
          <form className="space-y-4" onSubmit={submitManual}>
            <CardHeader>
              <CardTitle>Manual listing fallback</CardTitle>
            </CardHeader>
            <p className="text-sm text-[var(--color-text-muted)]">
              Provider retrieval failed. Save a clearly marked, unverified
              manual entry instead.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <TextField
                label="Title"
                onChange={(e) =>
                  setManual({ ...manual, title: e.target.value })
                }
                required
                value={manual.title}
              />
              <TextField
                label="Price"
                min="0"
                onChange={(e) =>
                  setManual({ ...manual, price: Number(e.target.value) })
                }
                required
                step="0.01"
                type="number"
                value={manual.price || ""}
              />
              <TextField
                label="Shipping"
                min="0"
                onChange={(e) =>
                  setManual({
                    ...manual,
                    shipping_price: Number(e.target.value),
                  })
                }
                step="0.01"
                type="number"
                value={manual.shipping_price || ""}
              />
              <SelectField
                label="Condition"
                onChange={(e) =>
                  setManual({
                    ...manual,
                    condition: e.target.value as Condition,
                  })
                }
                value={manual.condition}
              >
                <option value="new">New</option>
                <option value="used">Used</option>
                <option value="unknown">Unknown</option>
              </SelectField>
            </div>
            <button className="secondary-button" disabled={busy} type="submit">
              Save manual entry and analyze
            </button>
          </form>
        </Card>
      ) : null}
    </section>
  );
}

function Results({
  listing,
  analysis,
  onPortfolio,
  onWatchlist,
  portfolioMessage,
  watchlistMessage,
}: {
  listing: Listing;
  analysis: ListingAnalysis;
  onPortfolio: () => void;
  onWatchlist: () => void;
  portfolioMessage: string;
  watchlistMessage: string;
}) {
  const premiumOrDiscount = analysis.discount_percent
    ? `${percent(analysis.discount_percent)} discount`
    : analysis.premium_percent
      ? `${percent(analysis.premium_percent)} premium`
      : "--";
  return (
    <>
      <div className="page-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="metric-label">Listing decision</p>
            <h2 className="mt-1 text-xl font-bold">{listing.title}</h2>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              {listing.condition} ·{" "}
              {listing.is_complete === false
                ? "Incomplete"
                : "Completeness unconfirmed"}{" "}
              · {listing.is_verified ? "Provider verified" : "Manual entry"}
            </p>
          </div>
          <StatusBadge value={analysis.decision.toUpperCase()} />
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Total cost"
            value={currency(analysis.total_cost)}
          />
          <MetricCard
            label="Fair value range"
            value={`${currency(analysis.fair_value_low)} – ${currency(analysis.fair_value_high)}`}
          />
          <MetricCard label="Discount / premium" value={premiumOrDiscount} />
          <MetricCard
            label="Confidence"
            value={`${numberValue(analysis.decision_confidence)}/100`}
          />
          <MetricCard
            label="Market sample"
            value={numberValue(analysis.valuation_sample_size)}
          />
          <MetricCard
            label="Freshness"
            value={
              analysis.valuation_retrieved_at
                ? new Date(analysis.valuation_retrieved_at).toLocaleDateString()
                : "Unavailable"
            }
          />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            className="secondary-button"
            onClick={onWatchlist}
            type="button"
          >
            Save to watchlist
          </button>
          <button
            className="primary-button"
            onClick={onPortfolio}
            type="button"
          >
            Add to purchase portfolio
          </button>
        </div>
        {portfolioMessage || watchlistMessage ? (
          <p className="mt-3 text-sm text-[var(--color-text-muted)]">
            {portfolioMessage || watchlistMessage}
          </p>
        ) : null}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Risk flags</CardTitle>
          </CardHeader>
          <div className="flex flex-wrap gap-2">
            {analysis.risk_flags.length
              ? analysis.risk_flags.map((flag) => (
                  <span
                    className="rounded-full bg-[var(--color-surface-muted)] px-3 py-1 text-xs font-bold"
                    key={flag}
                  >
                    {flag.replace(/_/g, " ")}
                  </span>
                ))
              : "No material risk flags."}
          </div>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Reasons</CardTitle>
          </CardHeader>
          <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
            {analysis.reasons.map((reason) => (
              <li key={reason}>• {reason}</li>
            ))}
          </ul>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Score breakdown</CardTitle>
        </CardHeader>
        <pre className="overflow-auto rounded bg-[var(--color-surface-muted)] p-3 text-xs">
          {JSON.stringify(analysis.score_breakdown, null, 2)}
        </pre>
      </Card>
    </>
  );
}
