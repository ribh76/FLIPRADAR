import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { Logo } from "../../components/Logo";

export function UnauthorizedPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-8">
      <section className="w-full max-w-md rounded-[var(--radius-card)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-soft)]">
        <div className="mb-8 rounded-[var(--radius-card)] bg-brand-black p-4">
          <Logo />
        </div>
        <ShieldAlert className="text-[var(--color-accent-warm)]" size={28} />
        <p className="mt-5 text-sm font-semibold uppercase text-[var(--color-info)]">
          Access restricted
        </p>
        <h1 className="mt-2 text-3xl font-bold text-[var(--color-text)]">
          You don’t have access to this page
        </h1>
        <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
          Return to your dashboard or sign in with an account that has access.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link className="primary-button" to="/dashboard">Dashboard</Link>
          <Link className="secondary-button" to="/login">Sign in</Link>
        </div>
      </section>
    </main>
  );
}
