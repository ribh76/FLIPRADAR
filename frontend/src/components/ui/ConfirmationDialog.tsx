import { AlertTriangle } from "lucide-react";
import { Modal } from "./Modal";

export function ConfirmationDialog({
  confirmLabel = "Confirm",
  description,
  isBusy = false,
  isOpen,
  onCancel,
  onConfirm,
  title,
  tone = "danger",
}: {
  confirmLabel?: string;
  description: string;
  isBusy?: boolean;
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  tone?: "danger" | "neutral";
}) {
  return (
    <Modal isOpen={isOpen} onClose={onCancel} title={title}>
      <div className="flex items-start gap-3">
        <AlertTriangle
          className={
            tone === "danger"
              ? "text-[var(--color-warning)]"
              : "text-[var(--color-accent-warm)]"
          }
          size={21}
          aria-hidden="true"
        />
        <p className="text-sm leading-6 text-[var(--color-text-muted)]">
          {description}
        </p>
      </div>
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <button className="secondary-button" onClick={onCancel} type="button">
          Cancel
        </button>
        <button
          className={`primary-button ${tone === "danger" ? "bg-[var(--color-warning)] text-white hover:brightness-110" : ""}`}
          disabled={isBusy}
          onClick={onConfirm}
          type="button"
        >
          {isBusy ? "Working..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
