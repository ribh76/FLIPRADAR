const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const enabled = import.meta.env.VITE_ERROR_REPORTING_ENABLED === "true";

type ErrorPayload = {
  name: string;
  message: string;
  stack?: string;
  url: string;
};

function payloadFor(error: unknown): ErrorPayload {
  const normalized = error instanceof Error ? error : new Error(String(error));
  return {
    name: normalized.name,
    message: normalized.message.slice(0, 1000),
    stack: normalized.stack?.slice(0, 8000),
    url: window.location.href,
  };
}

export function reportFrontendError(error: unknown): void {
  if (!enabled) return;

  void fetch(`${apiBaseUrl}/client-errors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payloadFor(error)),
    keepalive: true,
  }).catch(() => undefined);
}

export function initializeErrorReporting(): void {
  if (!enabled) return;
  window.addEventListener("error", (event) => reportFrontendError(event.error));
  window.addEventListener("unhandledrejection", (event) =>
    reportFrontendError(event.reason),
  );
}
