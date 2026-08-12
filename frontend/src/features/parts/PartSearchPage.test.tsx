import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../services/apiClient";
import type { PartCatalogSearchResult } from "../../types";
import { PartSearchPage } from "./PartSearchPage";

vi.mock("../../services/apiClient", () => ({
  apiClient: { parts: { search: vi.fn() } },
  getApiError: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const part: PartCatalogSearchResult = {
  aliases: ["2x4 Brick"],
  available_colors: [],
  canonical_identifier: "part:3001",
  category: null,
  fetched_at: null,
  first_known_year: 1958,
  id: "part-3001",
  image_urls: [],
  last_known_year: null,
  market_price: "0.18",
  market_price_currency: "USD",
  match_confidence: "exact",
  match_explanation: "Exact part number match.",
  match_type: "exact_part_number",
  mold_variants: [{ description: "Solid studs", identifier: "3001a" }],
  name: "Brick 2 x 4",
  provider_identifiers: { bricklink: "3001" },
  quality_flags: [],
  source_name: "BrickLink",
  source_updated_at: null,
  source_url: null,
};

function renderPage(path = "/parts?query=3001") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <PartSearchPage />
    </MemoryRouter>,
  );
}

describe("PartSearchPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the match explanation, optional market price, and variants", async () => {
    vi.mocked(apiClient.parts.search).mockResolvedValue({
      pagination: { count: 1, has_more: false, limit: 12, offset: 0 },
      query: "3001",
      results: [part],
      source: "local",
    });

    renderPage();

    expect(await screen.findByText("Brick 2 x 4")).toBeInTheDocument();
    expect(screen.getByText("Exact part number match.")).toBeInTheDocument();
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText(/3001a — Solid studs/)).toBeInTheDocument();
  });

  it("shows search suggestions when no parts match", async () => {
    vi.mocked(apiClient.parts.search).mockResolvedValue({
      pagination: { count: 0, has_more: false, limit: 12, offset: 0 },
      query: "unknown",
      results: [],
      source: "local",
    });

    renderPage("/parts?query=unknown&color=Blue");

    expect(await screen.findByText("No matching parts")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Search without filters" }),
    ).toBeEnabled();
  });

  it("passes filters and pagination to the API", async () => {
    vi.mocked(apiClient.parts.search).mockResolvedValue({
      pagination: { count: 0, has_more: false, limit: 12, offset: 12 },
      query: "brick",
      results: [],
      source: "local",
    });

    renderPage(
      "/parts?query=brick&color=Red&category=Bricks&year=1958&offset=12",
    );

    await waitFor(() => {
      expect(apiClient.parts.search).toHaveBeenCalledWith(
        "brick",
        { category: "Bricks", color: "Red", limit: 12, offset: 12, year: 1958 },
        expect.any(AbortSignal),
      );
    });
  });
});
