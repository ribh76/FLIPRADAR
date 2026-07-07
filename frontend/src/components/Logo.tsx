import { Radar } from "lucide-react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-600 text-white shadow-sm">
        <Radar aria-hidden="true" size={22} />
      </div>
      {!compact && (
        <div>
          <div className="text-lg font-bold leading-none text-white">FlipRadar</div>
          <div className="mt-1 text-xs font-medium text-blue-100">
            LEGO set decisions without the spreadsheet fog
          </div>
        </div>
      )}
    </div>
  );
}
