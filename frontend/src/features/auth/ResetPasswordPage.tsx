import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient, getApiError } from "../../services/apiClient";
import { Logo } from "../../components/Logo";
import { FormAlert, TextField } from "../../components/ui";

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
      const response = await apiClient.auth.confirmPasswordReset({
        token,
        password,
      });
      setIsComplete(true);
      setMessage(response.message);
    } catch (error) {
      setMessage(getApiError(error));
    } finally {
      setIsLoading(false);
    }
  }

  return (
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
          <TextField
            autoComplete="new-password"
            label="New password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
          <FormAlert tone="neutral">{message}</FormAlert>
          <button
            className="primary-button w-full"
            disabled={isLoading}
            type="submit"
          >
            {isLoading ? "Resetting..." : "Reset password"}
          </button>
        </form>
      )}
    </section>
  );
}
