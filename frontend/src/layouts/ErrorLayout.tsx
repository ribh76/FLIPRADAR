import { AlertTriangle, Home } from "lucide-react";
import { useEffect } from "react";
import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Logo } from "../components/Logo";
import { reportFrontendError } from "../services/errorReporting";

export function ErrorLayout() {
  const error = useRouteError();
  useEffect(() => {
    reportFrontendError(error);
  }, [error]);
  const title = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : "Page not found";
  const message = isRouteErrorResponse(error)
    ? "The requested FlipRadar view could not be loaded."
    : "That route is not part of the current workspace.";

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-8">
      <section className="w-full max-w-md rounded-[var(--radius-card)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-soft)]">
        <div className="mb-8 rounded-[var(--radius-card)] bg-brand-black p-4">
          <Logo />
        </div>
        <div className="flex items-center gap-3">
          <AlertTriangle
            className="text-[var(--color-accent-warm)]"
            size={22}
            aria-hidden="true"
          />
          <p className="text-sm font-semibold uppercase tracking-normal text-[var(--color-info)]">
            Error
          </p>
        </div>
        <h1 className="mt-3 text-3xl font-bold text-[var(--color-text)]">
          {title}
        </h1>
        <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
          {message}
        </p>
        <Link className="primary-button mt-8 inline-flex px-5" to="/dashboard">
          <Home size={17} aria-hidden="true" />
          Dashboard
        </Link>
      </section>
    </main>
  );
}
