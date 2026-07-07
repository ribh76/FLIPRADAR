import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api, getApiError } from "../api/client";
import { HtmlTemplate } from "../components/HtmlTemplate";
import loginHtml from "../templates/login.html?raw";

export function LoginPage() {
  const navigate = useNavigate();

  const onMount = useCallback(
    (root: HTMLDivElement) => {
      const form = root.querySelector<HTMLFormElement>("[data-login-form]");
      const errorBox = root.querySelector<HTMLElement>("[data-error]");
      const loadingBar = root.querySelector<HTMLElement>("[data-loading-bar]");
      const submitButton = root.querySelector<HTMLButtonElement>("[data-submit]");
      const devPassButton = root.querySelector<HTMLButtonElement>("[data-dev-pass]");
      const registerButton = root.querySelector<HTMLButtonElement>("[data-mode='register']");

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
          submitButton.textContent = isLoading ? "Logging in..." : "Login";
        }
      };

      const handleDevPass = () => {
        localStorage.setItem("flipradar_token", "dev-pass-token");
        navigate("/dashboard");
      };

      const handleRegister = () => {
        showError("Registration toggle is present but disabled for this build.");
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
          const response = await api.post("/auth/login", {
            username_or_email: String(values.get("username_or_email") ?? ""),
            password: String(values.get("password") ?? "")
          });
          localStorage.setItem("flipradar_token", response.data.access_token);
          navigate("/dashboard");
        } catch (error) {
          showError(getApiError(error));
        } finally {
          setLoading(false);
        }
      };

      form?.addEventListener("submit", handleSubmit);
      devPassButton?.addEventListener("click", handleDevPass);
      registerButton?.addEventListener("click", handleRegister);

      return () => {
        form?.removeEventListener("submit", handleSubmit);
        devPassButton?.removeEventListener("click", handleDevPass);
        registerButton?.removeEventListener("click", handleRegister);
      };
    },
    [navigate]
  );

  return <HtmlTemplate html={loginHtml} onMount={onMount} />;
}
