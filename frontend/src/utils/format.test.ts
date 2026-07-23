import { describe, expect, it } from "vitest";

import { currency, numberValue, percent, signedCurrency } from "./format";

describe("format utilities", () => {
  it("formats currency and signed currency values", () => {
    expect(currency(149.99)).toBe("$150");
    expect(currency("2499")).toBe("$2,499");
    expect(signedCurrency(42)).toBe("+$42");
    expect(signedCurrency(-42)).toBe("-$42");
  });

  it("formats numbers and percentages", () => {
    expect(numberValue(1250)).toBe("1,250");
    expect(numberValue("3000")).toBe("3,000");
    expect(percent(12)).toBe("12.0%");
    expect(percent("7.25")).toBe("7.3%");
  });

  it("returns placeholders for missing or invalid values", () => {
    expect(currency(null)).toBe("--");
    expect(numberValue(undefined)).toBe("--");
    expect(percent("not a number")).toBe("--");
    expect(signedCurrency("")).toBe("--");
  });
});
