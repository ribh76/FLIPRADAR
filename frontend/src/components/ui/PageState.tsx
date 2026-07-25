import {
  AlertTriangle,
  LockKeyhole,
  PackageOpen,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";

type StateTone = "neutral" | "error" | "warning";

type PageStateProps = {
  action?: ReactNode;
  children?: ReactNode;
  icon?: ReactNode;
  title: string;
  tone?: StateTone;
};

const toneClass: Record<StateTone, string> = {
  error: "border-red-200 bg-red-50 text-red-900",
  neutral: "border-slate-200 bg-white text-slate-700",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
};

export function PageState({
  action,
  children,
  icon,
  title,
  tone = "neutral",
}: PageStateProps) {
  return (
    <section
      className={`rounded-lg border p-5 text-sm font-medium shadow-soft ${toneClass[tone]}`}
    >
      <div className="flex items-start gap-3">
        {icon ? <div className="mt-0.5 shrink-0">{icon}</div> : null}
        <div className="min-w-0">
          <h2 className="text-base font-bold text-slate-950">{title}</h2>
          {children ? <div className="mt-2 leading-6">{children}</div> : null}
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </section>
  );
}

export function LoadingState({ title = "Loading..." }: { title?: string }) {
  return (
    <PageState
      icon={<RefreshCw className="animate-spin text-blue-700" size={19} />}
      title={title}
    />
  );
}

export function ErrorState({
  message,
  onRetry,
  title = "Something went wrong",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <PageState
      action={
        onRetry ? (
          <button className="secondary-button" onClick={onRetry} type="button">
            Retry
          </button>
        ) : null
      }
      icon={<AlertTriangle className="text-red-700" size={20} />}
      title={title}
      tone="error"
    >
      {message}
    </PageState>
  );
}

export function EmptyState({
  message,
  title = "Nothing here yet",
}: {
  message?: string;
  title?: string;
}) {
  return (
    <PageState
      icon={<PackageOpen className="text-slate-500" size={20} />}
      title={title}
    >
      {message}
    </PageState>
  );
}

export function UnauthorizedState({
  message = "Sign in again to continue.",
  title = "Unauthorized",
}: {
  message?: string;
  title?: string;
}) {
  return (
    <PageState
      icon={<LockKeyhole className="text-amber-700" size={20} />}
      title={title}
      tone="warning"
    >
      {message}
    </PageState>
  );
}
