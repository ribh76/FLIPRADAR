import axios from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyAuthToken,
  clearAuthSession,
  getApiError,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeAuthSession,
} from "./apiClient";

describe("getApiError", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds the stored bearer token to API requests", () => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => "test-token"),
    });

    const config = applyAuthToken({
      headers: new axios.AxiosHeaders(),
    });

    expect(config.headers.Authorization).toBe("Bearer test-token");
  });

  it("stores and clears auth session tokens", () => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
    });

    storeAuthSession({
      access_token: "access-token",
      refresh_token: "refresh-token",
    });

    expect(getStoredAccessToken()).toBe("access-token");
    expect(getStoredRefreshToken()).toBe("refresh-token");

    clearAuthSession();

    expect(getStoredAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
  });

  it("returns a string API detail when provided", () => {
    const error = new axios.AxiosError("request failed");
    error.response = {
      config: { headers: new axios.AxiosHeaders() },
      data: { detail: "Invalid credentials" },
      headers: {},
      status: 401,
      statusText: "Unauthorized",
    };

    expect(getApiError(error)).toBe("Invalid credentials");
  });

  it("formats validation error details", () => {
    const error = new axios.AxiosError("validation failed");
    error.response = {
      config: { headers: new axios.AxiosHeaders() },
      data: {
        detail: [
          { msg: "Set number is required" },
          { msg: "Price must be positive" },
        ],
      },
      headers: {},
      status: 422,
      statusText: "Unprocessable Entity",
    };

    expect(getApiError(error)).toBe(
      "Set number is required, Price must be positive",
    );
  });

  it("falls back for unknown errors", () => {
    expect(getApiError(new Error("boom"))).toBe(
      "Something went wrong. Try again.",
    );
  });

  it("uses the Axios message when no structured detail exists", () => {
    const error = new axios.AxiosError("Network Error");

    expect(getApiError(error)).toBe("Network Error");
  });
});
