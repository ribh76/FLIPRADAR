import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge, verdictTone } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders the verdict label", () => {
    render(<StatusBadge value="WATCH" />);

    expect(screen.getByText("WATCH")).toBeInTheDocument();
  });

  it("maps known verdicts to stable tone classes", () => {
    expect(verdictTone("BUY")).toContain("emerald");
    expect(verdictTone("PASS")).toContain("red");
    expect(verdictTone("WATCH")).toContain("amber");
    expect(verdictTone("HOLD")).toContain("blue");
  });
});
