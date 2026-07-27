import { Radar } from "lucide-react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-control)] bg-brand-accent text-brand-black shadow-sm">
        <Radar aria-hidden="true" size={22} />
      </div>
      {!compact && (
        <div>
          <div className="text-lg font-black leading-none text-[var(--color-text-inverse)]">
            FlipRadar
          </div>
          <div className="mt-1 text-xs font-semibold text-[rgba(255,247,237,0.72)]">
            LEGO decisions, priced with signal
          </div>
        </div>
      )}
    </div>
  );
}
