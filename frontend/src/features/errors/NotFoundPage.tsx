import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Logo } from "../../components/Logo";

export function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-8">
      <section className="w-full max-w-md rounded-[var(--radius-card)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-soft)]">
        <div className="mb-8 rounded-[var(--radius-card)] bg-brand-black p-4">
          <Logo />
        </div>
        <Compass className="text-[var(--color-accent)]" size={28} />
        <p className="mt-5 text-sm font-semibold uppercase text-[var(--color-info)]">
          404
        </p>
        <h1 className="mt-2 text-3xl font-bold text-[var(--color-text)]">
          Page not found
        </h1>
        <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
          This link may be out of date, or the page may no longer exist.
        </p>
        <Link className="primary-button mt-8 inline-flex px-5" to="/dashboard">
          Go to dashboard
        </Link>
      </section>
    </main>
  );
}
