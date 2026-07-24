import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, getApiError } from "../api/client";
import { Logo } from "../components/Logo";

type VerificationState = "loading" | "success" | "error";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<VerificationState>("loading");
  const [message, setMessage] = useState("Verifying your email address...");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setState("error");
      setMessage("Verification link is missing a token.");
      return;
    }

    api
      .post("/auth/verify-email", { token })
      .then((response) => {
        setState("success");
        setMessage(response.data.message ?? "Email address verified.");
      })
      .catch((error: unknown) => {
        setState("error");
        setMessage(getApiError(error));
      });
  }, [searchParams]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-4 py-8">
      <section className="w-full max-w-md rounded-lg bg-white p-8 shadow-soft">
        <div className="mb-8">
          <Logo />
        </div>
        <p className="text-sm font-semibold uppercase tracking-normal text-blue-700">
          Email verification
        </p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">
          {state === "success" ? "You are verified" : "Verification status"}
        </h1>
        <p className="mt-4 text-sm leading-6 text-slate-600">{message}</p>
        <div className="mt-8">
          <Link className="primary-button inline-flex px-5" to="/login">
            Continue
          </Link>
        </div>
      </section>
    </main>
  );
}
