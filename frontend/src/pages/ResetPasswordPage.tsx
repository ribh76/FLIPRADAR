import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, getApiError } from "../api/client";
import { Logo } from "../components/Logo";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isComplete, setIsComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = searchParams.get("token");
    if (!token) {
      setMessage("Reset link is missing a token.");
      return;
    }

    setIsLoading(true);
    setMessage("");
    try {
      const response = await api.post("/auth/password-reset/confirm", {
        token,
        password,
      });
      setIsComplete(true);
      setMessage(response.data.message);
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-4 py-8">
      <section className="w-full max-w-md rounded-lg bg-white p-8 shadow-soft">
        <div className="mb-8">
          <Logo />
        </div>
        <p className="text-sm font-semibold uppercase tracking-normal text-blue-700">
          Account security
        </p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">
          Reset your password
        </h1>
        {isComplete ? (
          <div className="mt-6 space-y-5">
            <p className="text-sm leading-6 text-slate-600">{message}</p>
            <Link className="primary-button inline-flex px-5" to="/login">
              Continue
            </Link>
          </div>
        ) : (
          <form className="mt-6 space-y-5" onSubmit={submitReset}>
            <label className="block space-y-2">
              <span className="field-label">New password</span>
              <input
                className="field-input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
              />
            </label>
            {message ? (
              <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600">
                {message}
              </p>
            ) : null}
            <button
              className="primary-button w-full"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? "Resetting..." : "Reset password"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
