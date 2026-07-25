import { AlertTriangle, Home } from "lucide-react";
import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";
import { Logo } from "../components/Logo";

export function ErrorLayout() {
  const error = useRouteError();
  const title = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : "Page not found";
  const message = isRouteErrorResponse(error)
    ? "The requested FlipRadar view could not be loaded."
    : "That route is not part of the current workspace.";

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-4 py-8">
      <section className="w-full max-w-md rounded-lg bg-white p-8 shadow-soft">
        <div className="mb-8">
          <Logo />
        </div>
        <div className="flex items-center gap-3">
          <AlertTriangle
            className="text-amber-600"
            size={22}
            aria-hidden="true"
          />
          <p className="text-sm font-semibold uppercase tracking-normal text-blue-700">
            Error
          </p>
        </div>
        <h1 className="mt-3 text-3xl font-bold text-slate-950">{title}</h1>
        <p className="mt-4 text-sm leading-6 text-slate-600">{message}</p>
        <Link className="primary-button mt-8 inline-flex px-5" to="/dashboard">
          <Home size={17} aria-hidden="true" />
          Dashboard
        </Link>
      </section>
    </main>
  );
}
