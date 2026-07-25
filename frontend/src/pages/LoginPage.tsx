import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiClient, clearAuthSession, getApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

type AuthMode = "login" | "register";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuth();
  const [mode, setMode] = useState<AuthMode>(
    location.pathname === "/register" ? "register" : "login",
  );
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(
    "Errors and validation messages will appear here.",
  );
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMode(location.pathname === "/register" ? "register" : "login");
    setError("");
  }, [location.pathname]);

  const fromPath =
    typeof location.state === "object" &&
    location.state !== null &&
    "from" in location.state &&
    typeof location.state.from === "object" &&
    location.state.from !== null &&
    "pathname" in location.state.from &&
    typeof location.state.from.pathname === "string"
      ? location.state.from.pathname
      : "/dashboard";

  function selectMode(nextMode: AuthMode) {
    setMode(nextMode);
    navigate(nextMode === "login" ? "/login" : "/register", { replace: true });
  }

  function handleDevPass() {
    clearAuthSession();
    auth.login({ access_token: "dev-pass-token", refresh_token: "" });
    navigate("/dashboard");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      const response =
        mode === "login"
          ? await apiClient.auth.login({
              username_or_email: usernameOrEmail,
              password,
            })
          : await apiClient.auth.register({
              username,
              email,
              password,
            });
      auth.login(response);
      navigate(fromPath);
    } catch (submitError) {
      setError(getApiError(submitError));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="grid w-full max-w-5xl overflow-hidden rounded-lg bg-white shadow-soft lg:grid-cols-[0.95fr_1.05fr]">
      <div className="bg-navy-900 p-8 text-white sm:p-10">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-600 text-white shadow-sm">
            FR
          </div>
          <div>
            <div className="text-lg font-bold leading-none text-white">
              FlipRadar
            </div>
            <div className="mt-1 text-xs font-medium text-blue-100">
              LEGO set decisions without the spreadsheet fog
            </div>
          </div>
        </div>
        <div className="mt-20 max-w-sm">
          <h1 className="text-4xl font-bold tracking-normal">
            Buy, pass, hold, or sell with cleaner signals.
          </h1>
          <p className="mt-4 text-base leading-7 text-blue-100">
            FlipRadar turns LEGO set metadata, asking price, and market
            snapshots into fast collector decisions.
          </p>
        </div>
      </div>

      <div className="p-8 sm:p-10">
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-normal text-blue-700">
            Welcome back
          </p>
          <h2 className="mt-2 text-3xl font-bold text-slate-950">
            {mode === "login" ? "Sign in to FlipRadar" : "Create your account"}
          </h2>
        </div>

        <div className="mb-6 grid grid-cols-2 rounded-md bg-slate-100 p-1">
          <button
            className={`h-10 rounded-md text-sm font-bold ${mode === "login" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`}
            onClick={() => selectMode("login")}
            type="button"
          >
            Login
          </button>
          <button
            className={`h-10 rounded-md text-sm font-bold ${mode === "register" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`}
            onClick={() => selectMode("register")}
            type="button"
          >
            Register
          </button>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          {mode === "login" ? (
            <label className="block space-y-2">
              <span className="field-label">Username or email</span>
              <input
                autoComplete="username"
                className="field-input"
                onChange={(event) => setUsernameOrEmail(event.target.value)}
                value={usernameOrEmail}
              />
            </label>
          ) : (
            <>
              <label className="block space-y-2">
                <span className="field-label">Username</span>
                <input
                  autoComplete="username"
                  className="field-input"
                  onChange={(event) => setUsername(event.target.value)}
                  value={username}
                />
              </label>
              <label className="block space-y-2">
                <span className="field-label">Email</span>
                <input
                  autoComplete="email"
                  className="field-input"
                  onChange={(event) => setEmail(event.target.value)}
                  type="email"
                  value={email}
                />
              </label>
            </>
          )}
          <label className="block space-y-2">
            <span className="field-label">Password</span>
            <input
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              className="field-input"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>

          <div className="min-h-11 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600">
            {error}
          </div>

          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full bg-blue-600 transition-all duration-500 ${isLoading ? "w-full" : "w-0"}`}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <button
              className="primary-button w-full"
              disabled={isLoading}
              type="submit"
            >
              {isLoading
                ? mode === "login"
                  ? "Logging in..."
                  : "Creating..."
                : mode === "login"
                  ? "Login"
                  : "Register"}
            </button>
            <button
              className="secondary-button h-11 w-full border-blue-200 bg-blue-50 text-blue-800"
              onClick={handleDevPass}
              type="button"
            >
              Dev Pass
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
