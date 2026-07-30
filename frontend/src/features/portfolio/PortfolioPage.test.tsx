import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../services/apiClient";
import { invalidateServerState } from "../../hooks/serverState";
import type { PortfolioItem } from "../../types";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: {
    portfolio: {
      addItem: vi.fn(),
      deleteItem: vi.fn(),
      history: vi.fn(),
      list: vi.fn(),
      summary: vi.fn(),
      updateItem: vi.fn(),
    },
  },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const holding: PortfolioItem = {
  id: "holding-1",
  set_number: "10300",
  set_name: "Back to the Future Time Machine",
  quantity: 1,
  purchase_price: "100.00",
  purchase_date: "2024-01-10T00:00:00Z",
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
};

const collection = {
  data: [holding],
  pagination: { count: 1, has_more: false, limit: 25, offset: 0 },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <PortfolioPage />
    </MemoryRouter>,
  );
}

describe("PortfolioPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    invalidateServerState([
      "portfolio",
      JSON.stringify({ order: "purchase_date_desc", limit: 25, offset: 0 }),
    ]);
    invalidateServerState(["portfolio-history", "1m"]);
    invalidateServerState(["portfolio-history", "1w"]);
    vi.mocked(apiClient.portfolio.list).mockResolvedValue(collection);
    vi.mocked(apiClient.portfolio.summary).mockResolvedValue({
      total_items: 1,
      total_sets: 1,
      total_quantity: 1,
      total_cost_basis: "100.00",
      estimated_current_value: "200.00",
      unrealized_gain_loss: "100.00",
      unrealized_gain_loss_percent: "100.00",
    });
    vi.mocked(apiClient.portfolio.history).mockResolvedValue({
      range: "1m",
      points: [
        {
          timestamp: "2024-01-01T00:00:00Z",
          cost_basis: "100.00",
          market_value: "150.00",
          gain_loss: "50.00",
          currency: "USD",
        },
        {
          timestamp: "2024-01-02T00:00:00Z",
          cost_basis: "100.00",
          market_value: "200.00",
          gain_loss: "100.00",
          currency: "USD",
        },
      ],
    });
    vi.mocked(apiClient.portfolio.addItem).mockResolvedValue(holding);
    vi.mocked(apiClient.portfolio.updateItem).mockResolvedValue(holding);
    vi.mocked(apiClient.portfolio.deleteItem).mockResolvedValue();
  });

  it("sends the selected filter and sort controls to the portfolio endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findAllByText("Back to the Future Time Machine");

    await user.selectOptions(screen.getByLabelText("Performance"), "gain");
    await user.selectOptions(screen.getByLabelText("Sort"), "value_desc");

    await waitFor(() => {
      expect(apiClient.portfolio.list).toHaveBeenLastCalledWith(
        expect.objectContaining({
          performance: "gain",
          order: "value_desc",
          offset: 0,
          limit: 25,
        }),
      );
    });
  });

  it("opens the edit form and saves changed purchase details", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findAllByText("Back to the Future Time Machine");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const editDialog = screen.getByRole("dialog");
    const notes = within(editDialog).getByLabelText("Notes");
    await user.clear(notes);
    await user.type(notes, "Updated note");
    await user.click(
      within(editDialog).getByRole("button", { name: "Save changes" }),
    );

    await waitFor(() => {
      expect(apiClient.portfolio.updateItem).toHaveBeenCalledWith(
        "holding-1",
        expect.objectContaining({
          purchase_date: expect.stringMatching(/^2024-01-10T/),
          currency: "USD",
          notes: "Updated note",
        }),
      );
    });
  });

  it("confirms before deleting a holding", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findAllByText("Back to the Future Time Machine");

    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(apiClient.portfolio.deleteItem).toHaveBeenCalledWith("holding-1");
    });
  });

  it("loads portfolio history and updates the selected time range", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Portfolio value history");
    expect(await screen.findByText("Top performers")).toBeInTheDocument();
    expect(screen.getByText("Theme allocation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /analysis/i })).toHaveAttribute(
      "href",
      "/analyze",
    );

    await user.click(screen.getByRole("button", { name: "1W" }));
    await waitFor(() => {
      expect(apiClient.portfolio.history).toHaveBeenCalledWith("1w");
    });
  });

  it("shows a recoverable history error without hiding portfolio data", async () => {
    vi.mocked(apiClient.portfolio.history).mockRejectedValueOnce(
      new Error(
        "Portfolio history is unavailable until snapshots are recorded.",
      ),
    );
    renderPage();

    expect(await screen.findByText("History unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Portfolio history is unavailable until snapshots are recorded.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Back to the Future Time Machine").length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("labels insights as partial when another holdings page is available", async () => {
    vi.mocked(apiClient.portfolio.list).mockResolvedValue({
      ...collection,
      pagination: { ...collection.pagination, has_more: true },
    });
    renderPage();

    expect(
      await screen.findByText("Partial portfolio data"),
    ).toBeInTheDocument();
  });

  it("keeps the dashboard insight grids responsive", async () => {
    renderPage();

    expect(screen.getByTestId("portfolio-metrics")).toHaveClass(
      "sm:grid-cols-2",
      "xl:grid-cols-5",
    );
    expect(screen.getByTestId("portfolio-insight-grid")).toHaveClass(
      "xl:grid-cols-3",
    );
  });
});
