import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

export function Dropdown({
  children,
  label,
}: {
  children: ReactNode;
  label: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <div className="relative inline-block text-left" ref={rootRef}>
      <button
        aria-expanded={isOpen}
        className="secondary-button"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        {label}
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {isOpen ? (
        <div className="absolute right-0 z-20 mt-2 min-w-44 rounded-md border border-slate-200 bg-white p-1 shadow-soft">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function DropdownItem({
  children,
  onSelect,
}: {
  children: ReactNode;
  onSelect: () => void;
}) {
  return (
    <button
      className="flex w-full items-center rounded-md px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50"
      onClick={onSelect}
      type="button"
    >
      {children}
    </button>
  );
}
