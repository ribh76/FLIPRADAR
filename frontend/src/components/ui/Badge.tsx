import type { ReactNode } from "react";

type BadgeTone = "neutral" | "success" | "danger" | "warning" | "info";

const toneClass: Record<BadgeTone, string> = {
  danger:
    "border-[var(--color-warning)] bg-[rgba(145,3,3,0.1)] text-[var(--color-loss)]",
  info: "border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] text-[var(--color-info)]",
  neutral:
    "border-[var(--color-border-soft)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]",
  success:
    "border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] text-[var(--color-gain)]",
  warning:
    "border-[var(--color-accent-warm)] bg-[rgba(235,136,30,0.14)] text-[var(--color-accent-warm)]",
};

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-bold ${toneClass[tone]}`}
    >
      {children}
    </span>
  );
}
