import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../services/apiClient";
import type { PortfolioHoldingDetail } from "../../types";
import { HoldingDetailPage } from "./HoldingDetailPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: { portfolio: { detail: vi.fn(), updateItem: vi.fn() } },
}));

const detail: PortfolioHoldingDetail = {
  holding: {
    id: "holding-1",
    set_number: "10300",
    set_name: "Time Machine",
    quantity: 1,
    purchase_price: "100.00",
    purchase_date: "2025-01-10T00:00:00Z",
    currency: "USD",
    condition: "new",
    notes: "Original note",
    current_unit_value: "200.00",
    current_total_value: "200.00",
    cost_basis: "100.00",
    unrealized_gain_loss: "100.00",
    unrealized_gain_loss_percent: "100.00",
    valuation_status: "valued",
    valuation_confidence: "high",
    theme: "Icons",
  },
  portfolio_total_value: "300.00",
  portfolio_share_percent: "66.67",
  concentration_risk: {
    level: "high",
    message: "This holding represents a large share of the portfolio.",
    portfolio_share_percent: "66.67",
    value_rank: 1,
  },
  market_freshness_at: "2026-07-29T12:00:00Z",
  market_snapshots: [
    {
      timestamp: "2026-07-28T12:00:00Z",
      marketplace: "eBay",
      condition: "new",
      metric_type: "fair_market_value",
      value: "150.00",
      sample_size: 10,
      currency: "USD",
    },
    {
      timestamp: "2026-07-29T12:00:00Z",
      marketplace: "eBay",
      condition: "new",
      metric_type: "fair_market_value",
      value: "200.00",
      sample_size: 12,
      currency: "USD",
    },
  ],
  condition_pricing: [
    {
      condition: "new",
      estimated_unit_value: "200.00",
      confidence: "high",
      latest_snapshot_at: "2026-07-29T12:00:00Z",
    },
    {
      condition: "used",
      estimated_unit_value: "125.00",
      confidence: "medium",
      latest_snapshot_at: "2026-07-29T12:00:00Z",
    },
    {
      condition: "incomplete",
      estimated_unit_value: null,
      confidence: null,
      latest_snapshot_at: null,
    },
  ],
};

describe("HoldingDetailPage", () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.portfolio.detail).mockResolvedValue(detail);
    vi.mocked(apiClient.portfolio.updateItem).mockResolvedValue(detail.holding);
  });

  it("shows holding analytics and saves notes with purchase details", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/portfolio/items/holding-1"]}>
        <Routes>
          <Route
            path="/portfolio/items/:itemId"
            element={<HoldingDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Marketplace value history"),
    ).toBeInTheDocument();
    expect(screen.getByText("Condition price comparison")).toBeInTheDocument();
    expect(screen.getByText("Concentration risk")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Find deals" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Analyze holding" }),
    ).toBeInTheDocument();

    const notes = screen.getByLabelText("Notes");
    await waitFor(() => expect(notes).toHaveValue("Original note"));
    await user.clear(notes);
    await user.type(notes, "Updated note");
    await user.click(
      screen.getByRole("button", { name: "Save purchase details" }),
    );

    await waitFor(() =>
      expect(apiClient.portfolio.updateItem).toHaveBeenCalledWith(
        "holding-1",
        expect.objectContaining({ notes: "Updated note", purchase_price: 100 }),
      ),
    );
  });
});
