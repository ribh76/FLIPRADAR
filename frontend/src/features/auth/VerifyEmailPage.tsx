import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient, getApiError } from "../../services/apiClient";
import { Logo } from "../../components/Logo";

type VerificationState = "loading" | "success" | "error";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<VerificationState>("loading");
  const [message, setMessage] = useState("Verifying your email address...");

  useEffect(() => {
    const token = searchParams.get("token");
    const isEmailChange = searchParams.get("flow") === "email-change";
    if (!token) {
      setState("error");
      setMessage("Verification link is missing a token.");
      return;
    }

    const request = isEmailChange
      ? apiClient.auth.confirmEmailChange(token)
      : apiClient.auth.verifyEmail(token);

    request
      .then((response) => {
        setState("success");
        setMessage(response.message ?? "Email address verified.");
      })
      .catch((error: unknown) => {
        setState("error");
        setMessage(getApiError(error));
      });
  }, [searchParams]);

  return (
    <section className="w-full max-w-md rounded-[var(--radius-card)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-soft)]">
      <div className="mb-8 rounded-[var(--radius-card)] bg-brand-black p-4">
        <Logo />
      </div>
      <p className="text-sm font-semibold uppercase tracking-normal text-[var(--color-info)]">
        {searchParams.get("flow") === "email-change"
          ? "Email change"
          : "Email verification"}
      </p>
      <h1 className="mt-2 text-3xl font-bold text-[var(--color-text)]">
        {state === "success" ? "Confirmed" : "Verification status"}
      </h1>
      <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
        {message}
      </p>
      <div className="mt-8">
        <Link className="primary-button inline-flex px-5" to="/login">
          Continue
        </Link>
      </div>
    </section>
  );
}
