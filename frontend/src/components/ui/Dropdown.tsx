import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

export function Dropdown({
  children,
  label,
}: {
  children: ReactNode;
  label: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className="relative inline-block text-left"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setIsOpen(false);
        }
      }}
    >
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
        <div className="absolute right-0 z-20 mt-2 min-w-44 rounded-[var(--radius-control)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-1 shadow-[var(--shadow-soft)]">
          <div onClick={() => setIsOpen(false)}>{children}</div>
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
      className="flex w-full items-center rounded-[var(--radius-control)] px-3 py-2 text-left text-sm font-semibold text-[var(--color-text)] hover:bg-[var(--color-surface-muted)]"
      onClick={onSelect}
      type="button"
    >
      {children}
    </button>
  );
}
