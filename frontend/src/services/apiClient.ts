import axios from "axios";
import type { AxiosResponse, InternalAxiosRequestConfig } from "axios";
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  ApiMessage,
  AuthSession,
  CatalogSearchResponse,
  CollectionResponse,
  CurrentUser,
  DealFilters,
  DealsResponse,
  PortfolioItem,
  PortfolioItemCreate,
  PortfolioItemUpdate,
  PortfolioFilters,
  PortfolioDashboard,
  PortfolioHoldingDetail,
  PortfolioHistory,
  PortfolioSummary,
  RefreshSession,
  SavedSearch,
  LegoSet,
  Listing,
  ListingAnalysis,
  ManualListingEntry,
  SetDetail,
  WatchlistItem,
} from "../types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
const ACCESS_TOKEN_KEY = "flipradar_token";
const REFRESH_TOKEN_KEY = "flipradar_refresh_token";

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

type LoginRequest = {
  username_or_email: string;
  password: string;
};

type RegisterRequest = {
  username: string;
  email: string;
  password: string;
};

type UpdateProfileRequest = {
  display_name: string | null;
};

type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

type EmailChangeRequest = {
  new_email: string;
  current_password: string;
};

type PasswordResetConfirmRequest = {
  token: string;
  password: string;
};

type AccountDeletionResponse = ApiMessage & {
  deletion_scheduled_at: string;
};

type EmailVerificationResponse = ApiMessage & {
  verified: boolean;
};

type ResendVerificationResponse = ApiMessage & {
  sent: boolean;
  throttled: boolean;
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

async function requestData<TData>(
  request: Promise<AxiosResponse<TData>>,
): Promise<TData> {
  const response = await request;
  return response.data;
}

export const apiClient = {
  deals: {
    list(options: DealFilters = {}) {
      return requestData(
        api.get<DealsResponse>("/deals", {
          params: { limit: 25, offset: 0, ...options },
        }),
      );
    },
  },
  savedSearches: {
    list() {
      return requestData(api.get<SavedSearch[]>("/saved-searches"));
    },
    create(payload: { name: string; filter_config: DealFilters }) {
      return requestData(api.post<SavedSearch>("/saved-searches", payload));
    },
    update(
      id: string,
      payload: { name?: string; filter_config?: DealFilters },
    ) {
      return requestData(
        api.patch<SavedSearch>(`/saved-searches/${id}`, payload),
      );
    },
    duplicate(id: string) {
      return requestData(
        api.post<SavedSearch>(`/saved-searches/${id}/duplicate`),
      );
    },
    remove(id: string) {
      return requestData(api.delete<void>(`/saved-searches/${id}`));
    },
    recordRun(id: string) {
      return requestData(api.post<SavedSearch>(`/saved-searches/${id}/run`));
    },
  },
  analyze(payload: AnalyzeRequest) {
    return requestData(api.post<AnalyzeResponse>("/analyze", payload));
  },
  listings: {
    evaluate(payload: {
      set_number: string;
      url: string;
      manual_listing?: ManualListingEntry;
    }) {
      return requestData(api.post<Listing>("/listing-evaluations", payload));
    },
    analyze(listingId: string) {
      return requestData(
        api.post<ListingAnalysis>(`/listings/${listingId}/analysis`),
      );
    },
  },
  auth: {
    login(payload: LoginRequest) {
      return requestData(api.post<AuthSession>("/auth/login", payload));
    },
    register(payload: RegisterRequest) {
      return requestData(api.post<AuthSession>("/auth/register", payload));
    },
    resendVerification() {
      return requestData(
        api.post<ResendVerificationResponse>("/auth/resend-verification"),
      );
    },
    verifyEmail(token: string) {
      return requestData(
        api.post<EmailVerificationResponse>("/auth/verify-email", { token }),
      );
    },
    confirmEmailChange(token: string) {
      return requestData(
        api.post<EmailVerificationResponse>("/auth/email-change/confirm", {
          token,
        }),
      );
    },
    confirmPasswordReset(payload: PasswordResetConfirmRequest) {
      return requestData(
        api.post<ApiMessage>("/auth/password-reset/confirm", payload),
      );
    },
    logout: logoutCurrentSession,
  },
  users: {
    me() {
      return requestData(api.get<CurrentUser>("/users/me"));
    },
    updateMe(payload: UpdateProfileRequest) {
      return requestData(api.patch<CurrentUser>("/users/me", payload));
    },
    changePassword(payload: ChangePasswordRequest) {
      return requestData(api.post<ApiMessage>("/users/me/password", payload));
    },
    requestEmailChange(payload: EmailChangeRequest) {
      return requestData(
        api.post<ApiMessage>("/users/me/email-change/request", payload),
      );
    },
    listSessions() {
      return requestData(api.get<RefreshSession[]>("/users/me/sessions"));
    },
    revokeSession(sessionId: string) {
      return requestData(
        api.delete<ApiMessage>(`/users/me/sessions/${sessionId}`),
      );
    },
    revokeAllSessions() {
      return requestData(api.delete<ApiMessage>("/users/me/sessions"));
    },
    requestDeletion(currentPassword: string) {
      return requestData(
        api.post<AccountDeletionResponse>("/users/me/deletion-request", {
          current_password: currentPassword,
        }),
      );
    },
  },
  portfolio: {
    detail(itemId: string) {
      return requestData(
        api.get<PortfolioHoldingDetail>(`/portfolio/items/${itemId}/detail`),
      );
    },
    dashboard(filters: PortfolioFilters, range: PortfolioHistory["range"]) {
      return requestData(
        api.get<PortfolioDashboard>("/portfolio/dashboard", {
          params: { ...filters, range },
        }),
      );
    },
    list(filters: PortfolioFilters = {}) {
      return requestData(
        api.get<CollectionResponse<PortfolioItem>>("/portfolio", {
          params: filters,
        }),
      );
    },
    summary() {
      return requestData(api.get<PortfolioSummary>("/portfolio/summary"));
    },
    history(range: PortfolioHistory["range"]) {
      return requestData(
        api.get<PortfolioHistory>("/portfolio/history", { params: { range } }),
      );
    },
    addItem(payload: PortfolioItemCreate) {
      return requestData(api.post<PortfolioItem>("/portfolio/items", payload));
    },
    updateItem(itemId: string, payload: PortfolioItemUpdate) {
      return requestData(
        api.patch<PortfolioItem>(`/portfolio/items/${itemId}`, payload),
      );
    },
    deleteItem(itemId: string) {
      return requestData(api.delete<void>(`/portfolio/items/${itemId}`));
    },
  },
  watchlist: {
    list() {
      return requestData(api.get<WatchlistItem[]>("/watchlist"));
    },
    addSet(setNumber: string) {
      return requestData(
        api.post<WatchlistItem>("/watchlist", { set_number: setNumber }),
      );
    },
    addListing(listingId: string) {
      return requestData(
        api.post<WatchlistItem>("/watchlist", { listing_id: listingId }),
      );
    },
    refresh() {
      return requestData(api.post<WatchlistItem[]>("/watchlist/refresh"));
    },
    moveToPortfolio(itemId: string) {
      return requestData(
        api.post<PortfolioItem>(`/watchlist/${itemId}/move-to-portfolio`, {}),
      );
    },
    remove(itemId: string) {
      return requestData(api.delete<void>(`/watchlist/${itemId}`));
    },
  },
  sets: {
    list(query: string, limit = 8) {
      return requestData(
        api.get<CollectionResponse<LegoSet>>("/sets", {
          params: { limit, query },
        }),
      );
    },
    search(query: string, provider = "bricklink", limit = 25) {
      return requestData(
        api.get<CatalogSearchResponse>("/sets/search", {
          params: { limit, provider, query },
        }),
      );
    },
    detail(setNumber: string) {
      return requestData(
        api.get<SetDetail>(`/sets/${encodeURIComponent(setNumber)}`),
      );
    },
  },
};

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
