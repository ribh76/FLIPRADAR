import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PortfolioAnalysis } from "../../types";
import { apiClient } from "../../services/apiClient";
import { AnalyzePortfolioPage } from "./AnalyzePortfolioPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: {
    portfolio: {
      analyze: vi.fn(),
      analyses: vi.fn(),
      compareAnalyses: vi.fn(),
    },
  },
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

const history = {
  data: [
    {
      id: "analysis-2",
      generated_at: "2026-08-10T12:00:00Z",
      method_version: "portfolio-analysis-method-v1",
      prompt_version: "portfolio-analysis-v1",
      ai_narrative_status: "available" as const,
      portfolio_context: {},
      item_recommendations: analysis.item_recommendations,
      confidence_summary: analysis.confidence_summary,
      data_quality_warnings: analysis.data_quality_warnings,
    },
    {
      id: "analysis-1",
      generated_at: "2026-08-09T12:00:00Z",
      method_version: "portfolio-analysis-method-v1",
      prompt_version: "portfolio-analysis-v1",
      ai_narrative_status: "disabled" as const,
      portfolio_context: {},
      item_recommendations: analysis.item_recommendations,
      confidence_summary: analysis.confidence_summary,
      data_quality_warnings: [],
    },
  ],
  pagination: { count: 2, has_more: false, limit: 25, offset: 0 },
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
    vi.mocked(apiClient.portfolio.analyses).mockResolvedValue(history);
    vi.mocked(apiClient.portfolio.compareAnalyses).mockResolvedValue({
      previous_analysis_id: "analysis-1",
      current_analysis_id: "analysis-2",
      previous_generated_at: "2026-08-09T12:00:00Z",
      current_generated_at: "2026-08-10T12:00:00Z",
      changes: [
        {
          set_number: "900001",
          set_name: "Hold Set",
          previous_label: "hold",
          current_label: "watch",
          previous_confidence: "low",
          current_confidence: "medium",
          change_type: "changed",
          is_reversal: false,
        },
      ],
    });
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
    expect(screen.getByText("Previous analyses")).toBeInTheDocument();
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

  it("compares recommendation changes by set between prior analyses", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Previous analyses");

    await user.selectOptions(
      screen.getByLabelText("Earlier analysis"),
      "analysis-1",
    );
    await user.selectOptions(
      screen.getByLabelText("Later analysis"),
      "analysis-2",
    );
    await user.click(screen.getByRole("button", { name: "Compare analyses" }));

    expect(
      await screen.findByText("Recommendation changes by set"),
    ).toBeInTheDocument();
    expect(apiClient.portfolio.compareAnalyses).toHaveBeenCalledWith(
      "analysis-1",
      "analysis-2",
    );
    expect(screen.getAllByText("changed").length).toBeGreaterThan(0);
  });
});
