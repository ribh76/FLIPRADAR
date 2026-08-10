import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../services/apiClient";
import type { LegoSet } from "../../types";
import { SetsPage } from "./SetsPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: {
    sets: {
      list: vi.fn(),
      search: vi.fn(),
    },
  },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const catalogSet: LegoSet = {
  id: "set-42071",
  set_number: "42071",
  name: "Extreme Adventure",
  theme: "Technic",
  subtheme: null,
  release_year: 2018,
  retirement_year: 2018,
  piece_count: 2382,
  minifig_count: 0,
  msrp: "119.99",
  original_currency: "USD",
  region: "US",
  image_urls: null,
  source_name: "Bricklink catalog",
  source_url: "https://www.bricklink.com",
  data_quality_flag: true,
  completeness_flag: true,
  created_at: "2026-07-27T10:00:00Z",
  updated_at: "2026-07-27T10:00:00Z",
};

function renderPage(path = "/sets") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SetsPage />
    </MemoryRouter>,
  );
}

describe("SetsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.sets.list).mockResolvedValue({
      data: [],
      pagination: { count: 0, has_more: false, limit: 8, offset: 0 },
    });
  });

  it("offers known set numbers and names as autocomplete options", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.sets.list).mockResolvedValue({
      data: [catalogSet],
      pagination: { count: 1, has_more: false, limit: 8, offset: 0 },
    });

    renderPage();
    await user.type(screen.getByLabelText("Set number or name"), "420");

    await waitFor(() => {
      expect(document.querySelector('option[value="42071"]')).not.toBeNull();
      expect(
        document.querySelector('option[value="Extreme Adventure"]'),
      ).not.toBeNull();
    });
    expect(apiClient.sets.list).toHaveBeenCalledWith("420");
  });

  it("renders a loading card while a catalog search is pending", async () => {
    vi.mocked(apiClient.sets.search).mockReturnValue(new Promise(() => {}));

    renderPage("/sets?query=75192-loading");

    expect(
      await screen.findByText("Searching set catalog..."),
    ).toBeInTheDocument();
  });

  it("shows the no-result state for a not-found search", async () => {
    vi.mocked(apiClient.sets.search).mockRejectedValue(
      new Error("LEGO set was not found"),
    );

    renderPage("/sets?query=not-found-search");

    expect(await screen.findByText("No matching sets")).toBeInTheDocument();
    expect(screen.getByText(/try a different set number/i)).toBeInTheDocument();
  });

  it("shows a provider error state", async () => {
    vi.mocked(apiClient.sets.search).mockRejectedValue(
      new Error("Provider unavailable"),
    );

    renderPage("/sets?query=provider-failure");

    expect(
      await screen.findByText("Provider lookup unavailable"),
    ).toBeInTheDocument();
  });

  it("enables the watchlist action for catalog sets", async () => {
    vi.mocked(apiClient.sets.search).mockResolvedValue({
      query: "42071",
      provider: null,
      source: "local",
      exact_match: true,
      results: [catalogSet],
    });

    renderPage("/sets?query=42071-actions");

    expect(await screen.findByText("Extreme Adventure")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add to portfolio" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Add to watchlist" }),
    ).toBeEnabled();
  });
});
