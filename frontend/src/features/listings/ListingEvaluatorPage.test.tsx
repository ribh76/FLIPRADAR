import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ListingEvaluatorPage } from "./ListingEvaluatorPage";

const mocks = vi.hoisted(() => ({
  evaluate: vi.fn(),
  analyze: vi.fn(),
  addItem: vi.fn(),
}));

vi.mock("../../services/apiClient", () => ({
  apiClient: { listings: { evaluate: mocks.evaluate, analyze: mocks.analyze }, portfolio: { addItem: mocks.addItem } },
  getApiError: (error: unknown) => error instanceof Error ? error.message : "Request failed",
}));

describe("ListingEvaluatorPage", () => {
  it("retrieves an analysis and adds the listing to the purchase portfolio", async () => {
    const user = userEvent.setup();
    mocks.evaluate.mockResolvedValue({ id: "listing-1", title: "LEGO 75192 sealed complete", condition: "new", is_complete: true, is_verified: true, total_price: "520.00", currency: "USD", url: "https://www.ebay.com/itm/123" });
    mocks.analyze.mockResolvedValue({ id: "analysis-1", listing_id: "listing-1", fair_value: "725.00", fair_value_low: "680.00", fair_value_high: "760.00", total_cost: "520.00", discount_percent: "28.30", premium_percent: "0.00", product_match_confidence: "100.00", decision: "buy", decision_confidence: "91.00", reasons: ["Strong value."], risk_flags: [], score_breakdown: { score: 88 }, valuation_sample_size: 12, valuation_retrieved_at: "2026-08-06T12:00:00Z", created_at: "2026-08-06T12:00:00Z" });
    mocks.addItem.mockResolvedValue({});
    render(<ListingEvaluatorPage />);

    await user.type(screen.getByLabelText("Listing URL"), "https://www.ebay.com/itm/123456789012");
    await user.type(screen.getByLabelText("Set number"), "75192");
    await user.click(screen.getByRole("button", { name: "Evaluate listing" }));

    expect(await screen.findByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("$680 – $760")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /add to purchase portfolio/i }));
    await waitFor(() => expect(mocks.addItem).toHaveBeenCalledWith(expect.objectContaining({ set_number: "75192", purchase_price: 520 })));
  });
});
