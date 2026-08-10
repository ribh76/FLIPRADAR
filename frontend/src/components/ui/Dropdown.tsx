import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useId, useRef, useState } from "react";

export function Dropdown({
  children,
  label,
}: {
  children: ReactNode;
  label: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);

  function closeAndRestoreFocus() {
    setIsOpen(false);
    window.requestAnimationFrame(() => buttonRef.current?.focus());
  }

  function moveMenuFocus(direction: "first" | "last" | "next" | "previous") {
    const items = [
      ...(document
        .getElementById(menuId)
        ?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? []),
    ];
    if (!items.length) return;
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    if (direction === "first") return items[0].focus();
    if (direction === "last") return items[items.length - 1].focus();
    const offset = direction === "next" ? 1 : -1;
    items[(currentIndex + offset + items.length) % items.length].focus();
  }

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
        aria-haspopup="menu"
        aria-controls={isOpen ? menuId : undefined}
        className="secondary-button"
        onClick={() => setIsOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setIsOpen(true);
            window.requestAnimationFrame(() => {
              document
                .getElementById(menuId)
                ?.querySelector<HTMLButtonElement>("button")
                ?.focus();
            });
          }
          if (event.key === "Escape") closeAndRestoreFocus();
        }}
        ref={buttonRef}
        type="button"
      >
        {label}
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {isOpen ? (
        <div
          className="absolute right-0 z-20 mt-2 min-w-44 rounded-[var(--radius-control)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-1 shadow-[var(--shadow-soft)]"
          id={menuId}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              closeAndRestoreFocus();
            }
            if (event.key === "ArrowDown") {
              event.preventDefault();
              moveMenuFocus("next");
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              moveMenuFocus("previous");
            }
            if (event.key === "Home") {
              event.preventDefault();
              moveMenuFocus("first");
            }
            if (event.key === "End") {
              event.preventDefault();
              moveMenuFocus("last");
            }
          }}
          role="menu"
        >
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
      role="menuitem"
      type="button"
    >
      {children}
    </button>
  );
}
