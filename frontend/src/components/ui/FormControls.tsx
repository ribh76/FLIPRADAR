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
  return <p className="text-sm font-semibold text-red-700">{children}</p>;
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
        <p className="text-xs font-medium text-slate-500">{helpText}</p>
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
    error: "border-red-200 bg-red-50 text-red-800",
    neutral: "border-slate-200 bg-slate-50 text-slate-600",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[tone];
  return (
    <div className={`rounded-md border p-3 text-sm font-semibold ${className}`}>
      {children}
    </div>
  );
}
