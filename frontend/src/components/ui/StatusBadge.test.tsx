import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge, verdictTone } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders the verdict label", () => {
    render(<StatusBadge value="WATCH" />);

    expect(screen.getByText("WATCH")).toBeInTheDocument();
  });

  it("maps known verdicts to stable tone classes", () => {
    expect(verdictTone("BUY")).toContain("--color-gain");
    expect(verdictTone("PASS")).toContain("--color-loss");
    expect(verdictTone("WATCH")).toContain("--color-accent-warm");
    expect(verdictTone("HOLD")).toContain("--color-info");
  });
});
