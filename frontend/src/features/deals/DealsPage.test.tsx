import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { invalidateServerState } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import type { DealsResponse } from "../../types";
import { DealsPage } from "./DealsPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: { deals: { list: vi.fn() } },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const deals: DealsResponse = {
  data: [
    {
      listing_id: "listing-1",
      set_number: "75313",
      set_name: "AT-AT",
      marketplace: {
        name: "ebay",
        display_name: "eBay",
        base_url: "https://www.ebay.com",
        seller_name: "Brick Hunter",
        seller_rating: "99.8",
      },
      title: "LEGO 75313 AT-AT sealed",
      url: "https://www.ebay.com/itm/123",
      condition: "new",
      asking_price: "500.00",
      shipping_price: "20.00",
      total_cost: "520.00",
      currency: "USD",
      fair_value: "725.00",
      value: "725.00",
      valuation_sample_size: 12,
      score: 88,
      deal_band: "excellent",
      confidence_score: 93,
      confidence: 93,
      discount_percent: "28.3",
      discount: "28.3",
      last_seen_at: "2026-08-05T12:00:00Z",
      explanation: "Price is materially below the current fair value.",
    },
  ],
  pagination: { count: 1, has_more: false, limit: 25, offset: 0 },
  refresh: {
    requested: false,
    cached: false,
    throttled: false,
    retry_after_seconds: null,
    provider_errors: [],
  },
};

describe("DealsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateServerState(["deals", 25, 0]);
    vi.mocked(apiClient.deals.list).mockResolvedValue(deals);
  });

  afterEach(cleanup);

  it("renders deal value metrics and an external listing link", async () => {
    render(<DealsPage />, { wrapper: MemoryRouter });

    expect(await screen.findByText("AT-AT")).toBeInTheDocument();
    expect(screen.getByText("Estimated value")).toBeInTheDocument();
    expect(screen.getByText("$725")).toBeInTheDocument();
    expect(screen.getByText("28.3%")).toBeInTheDocument();
    expect(screen.getByText("93/100")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view listing/i })).toHaveAttribute(
      "href",
      "https://www.ebay.com/itm/123",
    );
  });

  it("keeps cards visible and labels partial provider results after refresh", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.deals.list)
      .mockResolvedValueOnce(deals)
      .mockResolvedValueOnce({
        ...deals,
        refresh: {
          ...deals.refresh,
          requested: true,
          provider_errors: ["Marketplace refresh failed for set 75313."],
        },
      });
    render(<DealsPage />, { wrapper: MemoryRouter });

    await screen.findByText("AT-AT");
    await user.click(screen.getByRole("button", { name: /refresh deals/i }));

    expect(
      await screen.findByText("Partial marketplace results"),
    ).toBeInTheDocument();
    expect(screen.getByText("AT-AT")).toBeInTheDocument();
    await waitFor(() => {
      expect(apiClient.deals.list).toHaveBeenLastCalledWith({ refresh: true });
    });
  });
});
