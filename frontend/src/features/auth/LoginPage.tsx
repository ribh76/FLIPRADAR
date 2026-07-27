import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  apiClient,
  clearAuthSession,
  getApiError,
} from "../../services/apiClient";
import { useAuth } from "../../auth/AuthProvider";
import { FormAlert, TextField } from "../../components/ui";

type AuthMode = "login" | "register";
const defaultAuthMessage = "Errors and validation messages will appear here.";

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
  const [error, setError] = useState(defaultAuthMessage);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMode(location.pathname === "/register" ? "register" : "login");
    setError(defaultAuthMessage);
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
    <section className="grid w-full max-w-5xl overflow-hidden rounded-[var(--radius-card)] bg-[var(--color-surface)] shadow-[var(--shadow-lifted)] lg:grid-cols-[0.95fr_1.05fr]">
      <div className="bg-brand-black p-8 text-[var(--color-text-inverse)] sm:p-10">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-control)] bg-brand-accent text-brand-black shadow-sm">
            FR
          </div>
          <div>
            <div className="text-lg font-black leading-none text-[var(--color-text-inverse)]">
              FlipRadar
            </div>
            <div className="mt-1 text-xs font-semibold text-[rgba(255,247,237,0.72)]">
              LEGO decisions, priced with signal
            </div>
          </div>
        </div>
        <div className="mt-20 max-w-sm">
          <h1 className="text-4xl font-black tracking-normal">
            Buy, pass, hold, or sell with cleaner signals.
          </h1>
          <p className="mt-4 text-base leading-7 text-[rgba(255,247,237,0.76)]">
            FlipRadar turns LEGO set metadata, asking price, and market
            snapshots into fast collector decisions.
          </p>
        </div>
      </div>

      <div className="p-8 sm:p-10">
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-normal text-[var(--color-info)]">
            Welcome back
          </p>
          <h2 className="mt-2 text-3xl font-bold text-[var(--color-text)]">
            {mode === "login" ? "Sign in to FlipRadar" : "Create your account"}
          </h2>
        </div>

        <div className="mb-6 grid grid-cols-2 rounded-[var(--radius-control)] bg-[var(--color-surface-muted)] p-1">
          <button
            className={`h-10 rounded-[var(--radius-control)] text-sm font-bold ${mode === "login" ? "bg-brand-accent text-brand-black shadow-sm" : "text-[var(--color-text-muted)]"}`}
            onClick={() => selectMode("login")}
            type="button"
          >
            Login
          </button>
          <button
            className={`h-10 rounded-[var(--radius-control)] text-sm font-bold ${mode === "register" ? "bg-brand-accent text-brand-black shadow-sm" : "text-[var(--color-text-muted)]"}`}
            onClick={() => selectMode("register")}
            type="button"
          >
            Register
          </button>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          {mode === "login" ? (
            <TextField
              autoComplete="username"
              label="Username or email"
              onChange={(event) => setUsernameOrEmail(event.target.value)}
              value={usernameOrEmail}
            />
          ) : (
            <>
              <TextField
                autoComplete="username"
                label="Username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
              <TextField
                autoComplete="email"
                label="Email"
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                value={email}
              />
            </>
          )}
          <TextField
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            label="Password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />

          <FormAlert tone={error === defaultAuthMessage ? "neutral" : "error"}>
            {error}
          </FormAlert>

          <div className="h-2 overflow-hidden rounded-full bg-[var(--color-surface-muted)]">
            <div
              className={`h-full rounded-full bg-brand-accent transition-all duration-500 ${isLoading ? "w-full" : "w-0"}`}
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
              className="secondary-button h-11 w-full"
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
