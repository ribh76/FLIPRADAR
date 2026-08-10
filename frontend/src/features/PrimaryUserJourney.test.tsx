import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DealsPage } from "./deals/DealsPage";
import { ListingEvaluatorPage } from "./listings/ListingEvaluatorPage";
import { SetsPage } from "./sets/SetsPage";

const mocks = vi.hoisted(() => ({
  addItem: vi.fn(),
  addListing: vi.fn(),
  addSet: vi.fn(),
  analyze: vi.fn(),
  deals: vi.fn(),
  evaluate: vi.fn(),
  savedSearches: vi.fn(),
  setList: vi.fn(),
  setSearch: vi.fn(),
}));

vi.mock("../services/apiClient", () => ({
  apiClient: {
    deals: { list: mocks.deals },
    listings: { analyze: mocks.analyze, evaluate: mocks.evaluate },
    portfolio: { addItem: mocks.addItem },
    savedSearches: { list: mocks.savedSearches },
    sets: { list: mocks.setList, search: mocks.setSearch },
    watchlist: { addListing: mocks.addListing, addSet: mocks.addSet },
  },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

describe("primary user journey", () => {
  it("finds a set, evaluates a matching deal, and adds it to a portfolio", async () => {
    const user = userEvent.setup();
    mocks.setList.mockResolvedValue({
      data: [],
      pagination: { count: 0, has_more: false, limit: 8, offset: 0 },
    });
    mocks.setSearch.mockResolvedValue({
      exact_match: true,
      provider: "bricklink",
      query: "75192",
      results: [
        {
          id: "set-75192",
          set_number: "75192",
          name: "Millennium Falcon",
          theme: "Star Wars",
          subtheme: null,
          release_year: 2017,
          retirement_year: null,
          piece_count: 7541,
          minifig_count: 4,
          msrp: "849.99",
          original_currency: "USD",
          region: "US",
          image_urls: null,
          source_name: null,
          source_url: null,
          data_quality_flag: false,
          completeness_flag: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      source: "local",
    });
    mocks.deals.mockResolvedValue({
      data: [
        {
          listing_id: "listing-1",
          set_number: "75192",
          set_name: "Millennium Falcon",
          marketplace: { display_name: "eBay", name: "ebay", seller_name: null, seller_rating: null, base_url: null },
          title: "LEGO 75192 sealed",
          url: "https://www.ebay.com/itm/123",
          condition: "new",
          is_sealed: true,
          asking_price: "600.00",
          shipping_price: "0.00",
          total_cost: "600.00",
          currency: "USD",
          fair_value: "750.00",
          value: "750.00",
          valuation_sample_size: 10,
          score: 85,
          deal_band: "strong",
          confidence_score: 90,
          confidence: 90,
          discount_percent: "20.00",
          discount: "20.00",
          last_seen_at: "2026-08-10T00:00:00Z",
          explanation: "Good value.",
        },
      ],
      pagination: { count: 1, has_more: false, limit: 25, offset: 0 },
      refresh: { requested: false, cached: false, throttled: false, retry_after_seconds: null, provider_errors: [] },
    });
    mocks.savedSearches.mockResolvedValue([]);
    mocks.evaluate.mockResolvedValue({
      id: "listing-1",
      title: "LEGO 75192 sealed",
      condition: "new",
      is_complete: true,
      is_verified: true,
      total_price: "600.00",
      currency: "USD",
      url: "https://www.ebay.com/itm/123",
    });
    mocks.analyze.mockResolvedValue({
      decision: "buy",
      decision_confidence: 90,
      discount_percent: "20.00",
      premium_percent: "0.00",
      fair_value_low: "700.00",
      fair_value_high: "800.00",
      total_cost: "600.00",
      valuation_sample_size: 10,
      valuation_retrieved_at: "2026-08-10T00:00:00Z",
      reasons: ["Good value."],
      risk_flags: [],
      score_breakdown: { score: 85 },
    });
    mocks.addItem.mockResolvedValue({});

    render(
      <MemoryRouter initialEntries={["/sets?query=75192"]}>
        <Routes>
          <Route path="/sets" element={<SetsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/listing-evaluator" element={<ListingEvaluatorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Millennium Falcon")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Find deals" }));
    expect(await screen.findByText("LEGO 75192 sealed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Evaluate listing" }));
    await user.click(screen.getByRole("button", { name: "Evaluate listing" }));
    expect(await screen.findByText("BUY")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Add to purchase portfolio" }),
    );
    await waitFor(() =>
      expect(mocks.addItem).toHaveBeenCalledWith(
        expect.objectContaining({ purchase_price: 600, set_number: "75192" }),
      ),
    );
  });
});
