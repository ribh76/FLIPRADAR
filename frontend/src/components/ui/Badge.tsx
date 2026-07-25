import type { ReactNode } from "react";

type BadgeTone = "neutral" | "success" | "danger" | "warning" | "info";

const toneClass: Record<BadgeTone, string> = {
  danger: "border-red-200 bg-red-100 text-red-800",
  info: "border-blue-200 bg-blue-100 text-blue-800",
  neutral: "border-slate-200 bg-slate-100 text-slate-700",
  success: "border-emerald-200 bg-emerald-100 text-emerald-800",
  warning: "border-amber-200 bg-amber-100 text-amber-900",
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
