import axios from "axios";
import type { AxiosResponse, InternalAxiosRequestConfig } from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const ACCESS_TOKEN_KEY = "flipradar_token";
const REFRESH_TOKEN_KEY = "flipradar_refresh_token";

type AuthSession = {
  access_token: string;
  refresh_token: string;
};

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

export const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

const refreshApi = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshPromise: Promise<string | null> | null = null;

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeAuthSession(session: AuthSession): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
}

export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function applyAuthToken(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

api.interceptors.request.use(applyAuthToken);

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return null;
  }
  if (!refreshPromise) {
    refreshPromise = refreshApi
      .post<AuthSession>("/auth/refresh", { refresh_token: refreshToken })
      .then((response: AxiosResponse<AuthSession>) => {
        storeAuthSession(response.data);
        return response.data.access_token;
      })
      .catch(() => {
        clearAuthSession();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) {
      throw error;
    }

    const originalRequest = error.config as RetriableRequestConfig | undefined;
    if (!originalRequest || originalRequest._retry) {
      throw error;
    }

    const requestUrl = String(originalRequest.url ?? "");
    if (
      requestUrl.includes("/auth/login") ||
      requestUrl.includes("/auth/register") ||
      requestUrl.includes("/auth/refresh") ||
      requestUrl.includes("/auth/logout")
    ) {
      throw error;
    }

    originalRequest._retry = true;
    const accessToken = await refreshAccessToken();
    if (!accessToken) {
      throw error;
    }

    const headers = new axios.AxiosHeaders(originalRequest.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    originalRequest.headers = headers;
    return api(originalRequest);
  },
);

export async function logoutCurrentSession(): Promise<void> {
  const refreshToken = getStoredRefreshToken();
  try {
    if (getStoredAccessToken()) {
      await api.post("/auth/logout", {
        refresh_token: refreshToken,
      });
    }
  } finally {
    clearAuthSession();
  }
}

export function getApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item.msg ?? "Invalid field").join(", ");
    }
    return error.message;
  }
  return "Something went wrong. Try again.";
}
