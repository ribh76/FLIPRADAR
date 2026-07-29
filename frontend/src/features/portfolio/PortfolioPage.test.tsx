import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../services/apiClient";
import type { PortfolioItem } from "../../types";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: {
    portfolio: {
      addItem: vi.fn(),
      deleteItem: vi.fn(),
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
};

const collection = {
  data: [holding],
  pagination: { count: 1, has_more: false, limit: 25, offset: 0 },
};

function renderPage() {
  return render(<PortfolioPage />);
}

describe("PortfolioPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
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
});
