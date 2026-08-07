import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { invalidateServerState } from "../../hooks/serverState";
import { WatchlistPage } from "./WatchlistPage";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  refresh: vi.fn(),
  move: vi.fn(),
  remove: vi.fn(),
  history: vi.fn(),
  replacements: vi.fn(),
}));
vi.mock("../../services/apiClient", () => ({
  apiClient: {
    watchlist: {
      list: mocks.list,
      refresh: mocks.refresh,
      moveToPortfolio: mocks.move,
      remove: mocks.remove,
      history: mocks.history,
      replacements: mocks.replacements,
    },
  },
  getApiError: () => "Request failed",
}));

const item = {
  id: "watch-1",
  user_id: "user-1",
  entry_type: "listing",
  set_number: "75192",
  listing_id: "listing-1",
  target_price: "600.00",
  notes: null,
  saved_at: "2026-08-06T10:00:00Z",
  last_known_listing_price: "520.00",
  last_known_listing_status: "active",
  current_price: "520.00",
  valuation: "725.00",
  discount_percent: "28.28",
  deal_score: 82,
  price_change: null,
  is_under_target: true,
  recommendation: "BUY",
  last_checked_at: "2026-08-06T12:00:00Z",
} as const;

describe("WatchlistPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateServerState(["watchlist"]);
  });
  it("refreshes display data and moves an active listing to the portfolio", async () => {
    const user = userEvent.setup();
    mocks.list.mockResolvedValue([item]);
    mocks.refresh.mockResolvedValue([{ ...item, current_price: "510.00" }]);
    mocks.move.mockResolvedValue({});
    mocks.history.mockResolvedValue([
      {
        observed_at: "2026-08-06T12:00:00Z",
        listing_price: "520.00",
        fair_value: "725.00",
        deal_score: 82,
        listing_status: "active",
      },
    ]);
    render(<WatchlistPage />);
    expect(await screen.findByText("Marketplace listing")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh all" }));
    await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Price history" }));
    expect(
      await screen.findByLabelText("Price history chart"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Move to portfolio" }));
    await waitFor(() => expect(mocks.move).toHaveBeenCalledWith("watch-1"));
  });

  it("keeps ended listings visible without a move action", async () => {
    const user = userEvent.setup();
    mocks.replacements.mockResolvedValue([
      {
        listing_id: "replacement-1",
        title: "Replacement listing",
        url: "https://example.com/listing",
        total_price: "510.00",
        currency: "USD",
        fair_value: "725.00",
        deal_score: 85,
        recommendation: "BUY",
      },
    ]);
    mocks.list.mockResolvedValue([
      { ...item, last_known_listing_status: "ended" },
    ]);
    render(<WatchlistPage />);
    expect(await screen.findByText(/no longer available/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Move to portfolio" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /find replacements/i }),
    );
    expect(
      await screen.findByRole("link", { name: /replacement listing/i }),
    ).toBeInTheDocument();
  });
});
