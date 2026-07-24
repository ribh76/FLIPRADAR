import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  api,
  clearAuthSession,
  getApiError,
  storeAuthSession,
} from "../api/client";
import { HtmlTemplate } from "../components/HtmlTemplate";
import loginHtml from "../templates/login.html?raw";

type AuthMode = "login" | "register";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const onMount = useCallback(
    (root: HTMLDivElement) => {
      let mode: AuthMode =
        window.location.pathname === "/register" ? "register" : "login";
      const form = root.querySelector<HTMLFormElement>("[data-login-form]");
      const errorBox = root.querySelector<HTMLElement>("[data-error]");
      const loadingBar = root.querySelector<HTMLElement>("[data-loading-bar]");
      const submitButton =
        root.querySelector<HTMLButtonElement>("[data-submit]");
      const devPassButton =
        root.querySelector<HTMLButtonElement>("[data-dev-pass]");
      const loginButton = root.querySelector<HTMLButtonElement>(
        "[data-mode='login']",
      );
      const registerButton = root.querySelector<HTMLButtonElement>(
        "[data-mode='register']",
      );
      const loginFields =
        root.querySelectorAll<HTMLElement>("[data-login-field]");
      const registerFields = root.querySelectorAll<HTMLElement>(
        "[data-register-field]",
      );
      const title = root.querySelector<HTMLElement>("[data-auth-title]");

      const showError = (message: string) => {
        if (errorBox) {
          errorBox.textContent = message;
        }
      };

      const setLoading = (isLoading: boolean) => {
        loadingBar?.classList.toggle("w-full", isLoading);
        loadingBar?.classList.toggle("w-0", !isLoading);
        if (submitButton) {
          submitButton.disabled = isLoading;
          submitButton.textContent = isLoading
            ? mode === "login"
              ? "Logging in..."
              : "Creating..."
            : mode === "login"
              ? "Login"
              : "Register";
        }
      };

      const setMode = (nextMode: AuthMode) => {
        mode = nextMode;
        const isLogin = mode === "login";
        loginFields.forEach((field) => {
          field.classList.toggle("hidden", !isLogin);
          field.classList.toggle("block", isLogin);
        });
        registerFields.forEach((field) => {
          field.classList.toggle("hidden", isLogin);
          field.classList.toggle("block", !isLogin);
        });
        loginButton?.classList.toggle("bg-white", isLogin);
        loginButton?.classList.toggle("text-slate-950", isLogin);
        loginButton?.classList.toggle("shadow-sm", isLogin);
        loginButton?.classList.toggle("text-slate-500", !isLogin);
        registerButton?.classList.toggle("bg-white", !isLogin);
        registerButton?.classList.toggle("text-slate-950", !isLogin);
        registerButton?.classList.toggle("shadow-sm", !isLogin);
        registerButton?.classList.toggle("text-slate-500", isLogin);
        if (title) {
          title.textContent = isLogin
            ? "Sign in to FlipRadar"
            : "Create your account";
        }
        if (submitButton) {
          submitButton.textContent = isLogin ? "Login" : "Register";
        }
        showError("");
      };

      const handleDevPass = () => {
        clearAuthSession();
        localStorage.setItem("flipradar_token", "dev-pass-token");
        navigate("/dashboard");
      };

      const handleRegister = () => {
        setMode("register");
        navigate("/register", { replace: true });
      };

      const handleLoginMode = () => {
        setMode("login");
        navigate("/login", { replace: true });
      };

      const handleSubmit = async (event: SubmitEvent) => {
        event.preventDefault();
        if (!form) {
          return;
        }
        const values = new FormData(form);
        setLoading(true);
        showError("");
        try {
          const password = String(values.get("password") ?? "");
          const response =
            mode === "login"
              ? await api.post("/auth/login", {
                  username_or_email: String(
                    values.get("username_or_email") ?? "",
                  ),
                  password,
                })
              : await api.post("/auth/register", {
                  username: String(values.get("username") ?? ""),
                  email: String(values.get("email") ?? ""),
                  password,
                });
          storeAuthSession(response.data);
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
          navigate(fromPath);
        } catch (error) {
          showError(getApiError(error));
        } finally {
          setLoading(false);
        }
      };

      setMode(mode);
      form?.addEventListener("submit", handleSubmit);
      devPassButton?.addEventListener("click", handleDevPass);
      loginButton?.addEventListener("click", handleLoginMode);
      registerButton?.addEventListener("click", handleRegister);

      return () => {
        form?.removeEventListener("submit", handleSubmit);
        devPassButton?.removeEventListener("click", handleDevPass);
        loginButton?.removeEventListener("click", handleLoginMode);
        registerButton?.removeEventListener("click", handleRegister);
      };
    },
    [location.state, navigate],
  );

  return <HtmlTemplate html={loginHtml} onMount={onMount} />;
}
