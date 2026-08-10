import type { Verdict } from "../../types";

export function verdictTone(verdict: Verdict | string) {
  if (verdict === "BUY" || verdict === "SELL") {
    return "bg-[rgba(73,252,226,0.12)] text-[var(--color-gain)] border-[var(--color-accent)]";
  }
  if (verdict === "PASS") {
    return "bg-[rgba(145,3,3,0.1)] text-[var(--color-loss)] border-[var(--color-warning)]";
  }
  if (verdict === "WATCH") {
    return "bg-[rgba(235,136,30,0.14)] text-[var(--color-accent-warm)] border-[var(--color-accent-warm)]";
  }
  return "bg-[var(--color-surface-muted)] text-[var(--color-info)] border-[var(--color-border-soft)]";
}

export function StatusBadge({ value }: { value: string }) {
  return (
    <span
      aria-label={`Status: ${value}`}
      className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-bold ${verdictTone(value)}`}
    >
      {value}
    </span>
  );
}
