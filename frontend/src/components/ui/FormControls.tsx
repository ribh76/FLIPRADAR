import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

type FieldShellProps = {
  children: ReactNode;
  className?: string;
  error?: string;
  helpText?: string;
  label: string;
};

export function ValidationMessage({ children }: { children?: ReactNode }) {
  if (!children) {
    return null;
  }
  return (
    <p className="text-sm font-semibold text-[var(--color-warning)]">
      {children}
    </p>
  );
}

export function FieldShell({
  children,
  className = "",
  error,
  helpText,
  label,
}: FieldShellProps) {
  return (
    <label className={`block space-y-2 ${className}`}>
      <span className="field-label">{label}</span>
      {children}
      {error ? (
        <ValidationMessage>{error}</ValidationMessage>
      ) : helpText ? (
        <p className="text-xs font-medium text-[var(--color-text-muted)]">
          {helpText}
        </p>
      ) : null}
    </label>
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  containerClassName?: string;
  error?: string;
  helpText?: string;
  label: string;
};

export function TextField({
  containerClassName,
  error,
  helpText,
  label,
  ...props
}: TextFieldProps) {
  return (
    <FieldShell
      className={containerClassName}
      error={error}
      helpText={helpText}
      label={label}
    >
      <input
        {...props}
        className={`field-input ${props.className ?? ""}`}
        aria-invalid={Boolean(error)}
      />
    </FieldShell>
  );
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  children: ReactNode;
  containerClassName?: string;
  error?: string;
  helpText?: string;
  label: string;
};

export function SelectField({
  children,
  containerClassName,
  error,
  helpText,
  label,
  ...props
}: SelectFieldProps) {
  return (
    <FieldShell
      className={containerClassName}
      error={error}
      helpText={helpText}
      label={label}
    >
      <select
        {...props}
        className={`field-input ${props.className ?? ""}`}
        aria-invalid={Boolean(error)}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export function FormAlert({
  children,
  tone = "error",
}: {
  children?: ReactNode;
  tone?: "error" | "neutral" | "success";
}) {
  if (!children) {
    return null;
  }
  const className = {
    error:
      "border-[var(--color-warning)] bg-[rgba(145,3,3,0.1)] text-[var(--color-loss)]",
    neutral:
      "border-[var(--color-border-soft)] bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]",
    success:
      "border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] text-[var(--color-gain)]",
  }[tone];
  return (
    <div className={`rounded-md border p-3 text-sm font-semibold ${className}`}>
      {children}
    </div>
  );
}
