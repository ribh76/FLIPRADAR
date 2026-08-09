import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PortfolioAnalysis } from "../../types";
import { apiClient } from "../../services/apiClient";
import { AnalyzePortfolioPage } from "./AnalyzePortfolioPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: { portfolio: { analyze: vi.fn() } },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const analysis: PortfolioAnalysis = {
  id: "analysis-1",
  generated_at: "2026-08-09T12:00:00Z",
  analytics: {
    holding_count: 2,
    valued_holding_count: 1,
    total_cost_basis: "300.00",
    total_market_value: "320.00",
    currency: "USD",
    summary_metrics: {
      concentration: {
        level: "high",
        largest_holding_percent: "62.50",
        top_three_percent: "100.00",
      },
      diversification: {
        distinct_sets: 2,
        distinct_themes: 2,
        value_coverage_percent: "50.00",
      },
      signals: { hold: 1, watch: 1, sell_consideration: 0 },
      top_performers: [{ set_number: "900001", set_name: "Rising Set" }],
    },
  },
  item_recommendations: [
    {
      portfolio_item_id: "holding-2",
      set_number: "900002",
      set_name: "Watch Set",
      label: "watch",
      priority: 2,
      confidence: "medium",
      reason_codes: ["price_trend_flat"],
      data_quality_flags: [],
    },
    {
      portfolio_item_id: "holding-1",
      set_number: "900001",
      set_name: "Hold Set",
      label: "hold",
      priority: 4,
      confidence: "low",
      reason_codes: ["missing_fair_value"],
      data_quality_flags: ["insufficient_market_data"],
    },
  ],
  confidence_summary: {
    overall: "low",
    item_counts: { high: 0, medium: 1, low: 1 },
  },
  data_quality_warnings: [
    {
      code: "insufficient_market_data",
      affected_holding_count: 1,
      message:
        "Some holdings do not have enough market data for a current valuation.",
    },
  ],
  ai_narrative: {
    executive_summary: "The calculated portfolio merits careful review.",
    diversification_observations: [
      {
        source_metric: "portfolio.diversification",
        text: "The current mix has limited diversification.",
      },
    ],
    concentration_observations: [
      {
        source_metric: "portfolio.concentration",
        text: "The calculated concentration merits attention.",
      },
    ],
    prioritized_actions: [
      {
        item_key: "holding-2",
        label: "watch",
        priority: 2,
        text: "Keep this holding under review.",
      },
    ],
    uncertainties: [],
    prompt_version: "portfolio-analysis-v1",
  },
  ai_narrative_status: "available",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalyzePortfolioPage />
    </MemoryRouter>,
  );
}

describe("AnalyzePortfolioPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.portfolio.analyze).mockResolvedValue(analysis);
  });

  it("shows the summary, risks, opportunities, actions, and disclaimer", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Analyze portfolio" }));

    expect(await screen.findByText("Executive summary")).toBeInTheDocument();
    expect(
      screen.getByText("Portfolio-wide opportunities"),
    ).toBeInTheDocument();
    expect(screen.getByText("Portfolio-wide risks")).toBeInTheDocument();
    expect(screen.getByText("Prioritized actions")).toBeInTheDocument();
    expect(screen.getByText("Item recommendations")).toBeInTheDocument();
    expect(
      screen.getByText("Collectibles-market disclaimer"),
    ).toBeInTheDocument();
    expect(apiClient.portfolio.analyze).toHaveBeenCalledOnce();
  });

  it("sorts item recommendations by set number", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Analyze portfolio" }));
    await screen.findAllByText("Watch Set");

    await user.selectOptions(
      screen.getByLabelText("Sort recommendations"),
      "set",
    );

    await waitFor(() => {
      const rows = screen.getAllByRole("row");
      expect(rows[1]).toHaveTextContent("900001");
      expect(rows[2]).toHaveTextContent("900002");
    });
  });
});
