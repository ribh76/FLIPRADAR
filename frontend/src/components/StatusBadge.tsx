import type { Verdict } from "../types";

export function verdictTone(verdict: Verdict | string) {
  if (verdict === "BUY" || verdict === "SELL") {
    return "bg-emerald-100 text-emerald-800 border-emerald-200";
  }
  if (verdict === "PASS") {
    return "bg-red-100 text-red-800 border-red-200";
  }
  if (verdict === "WATCH") {
    return "bg-amber-100 text-amber-900 border-amber-200";
  }
  return "bg-blue-100 text-blue-800 border-blue-200";
}

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-bold ${verdictTone(value)}`}>
      {value}
    </span>
  );
}
