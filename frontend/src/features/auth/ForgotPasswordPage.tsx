import type { FormEvent } from "react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../../components/Logo";
import { FormAlert, TextField } from "../../components/ui";
import { apiClient, getApiError } from "../../services/apiClient";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setMessage("");
    try {
      const response = await apiClient.auth.requestPasswordReset({ email });
      setMessage(response.message);
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="w-full max-w-md rounded-[var(--radius-card)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-soft)]">
      <div className="mb-8 rounded-[var(--radius-card)] bg-brand-black p-4">
        <Logo />
      </div>
      <p className="text-sm font-semibold uppercase tracking-normal text-[var(--color-info)]">
        Account security
      </p>
      <h1 className="mt-2 text-3xl font-bold text-[var(--color-text)]">
        Reset your password
      </h1>
      <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">
        Enter your email and we’ll send a reset link if an account exists.
      </p>
      <form className="mt-6 space-y-5" onSubmit={submitRequest}>
        <TextField
          autoComplete="email"
          label="Email"
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          value={email}
        />
        <FormAlert tone="neutral">{message}</FormAlert>
        <button
          className="primary-button w-full"
          disabled={isLoading}
          type="submit"
        >
          {isLoading ? "Sending..." : "Send reset link"}
        </button>
      </form>
      <Link
        className="mt-6 inline-flex text-sm font-semibold text-[var(--color-info)] hover:underline"
        to="/login"
      >
        Back to login
      </Link>
    </section>
  );
}
