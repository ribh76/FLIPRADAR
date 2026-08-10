import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useId, useRef } from "react";

export function Modal({
  children,
  isOpen,
  onClose,
  title,
}: {
  children: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  title: string;
}) {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (isOpen) {
      previouslyFocused.current = document.activeElement as HTMLElement;
      closeButtonRef.current?.focus();
    }
    return () => previouslyFocused.current?.focus();
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-end justify-center bg-brand-black/75 px-4 py-4 sm:items-center sm:py-8"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onClose();
        }
        if (event.key === "Tab") {
          const focusable = modalRef.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          );
          if (!focusable?.length) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }}
      ref={modalRef}
      role="dialog"
      tabIndex={-1}
    >
      <section className="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-[var(--radius-card)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-lifted)]">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold text-[var(--color-text)]" id={titleId}>
            {title}
          </h2>
          <button
            aria-label="Close"
            className="secondary-button h-9 w-9 px-0"
            onClick={onClose}
            ref={closeButtonRef}
            type="button"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>
        <div className="mt-5">{children}</div>
      </section>
    </div>
  );
}
