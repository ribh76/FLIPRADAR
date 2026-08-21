import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Logo } from "../../components/Logo";
import { FormAlert, TextField } from "../../components/ui";
import { apiClient, getApiError } from "../../services/apiClient";

export function MfaResetPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setMessage("");
    try {
      const response = token
        ? await apiClient.auth.confirmMfaReset(token)
        : await apiClient.auth.requestMfaReset({ email });
      setMessage(response.message);
      setIsComplete(Boolean(token));
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
        Reset MFA
      </h1>
      {isComplete ? (
        <div className="mt-6 space-y-5">
          <p className="text-sm leading-6 text-[var(--color-text-muted)]">
            {message}
          </p>
          <Link className="primary-button inline-flex px-5" to="/login">
            Continue
          </Link>
        </div>
      ) : (
        <form className="mt-6 space-y-5" onSubmit={submit}>
          {token ? (
            <p className="text-sm leading-6 text-[var(--color-text-muted)]">
              Confirming will disable MFA and end active sessions.
            </p>
          ) : (
            <TextField
              autoComplete="email"
              label="Email"
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              value={email}
            />
          )}
          <FormAlert tone="neutral">{message}</FormAlert>
          <button
            className="primary-button w-full"
            disabled={isLoading}
            type="submit"
          >
            {isLoading
              ? "Processing..."
              : token
                ? "Reset MFA"
                : "Send MFA reset link"}
          </button>
        </form>
      )}
      <Link
        className="mt-6 inline-flex text-sm font-semibold text-[var(--color-info)] hover:underline"
        to="/login"
      >
        Back to login
      </Link>
    </section>
  );
}
