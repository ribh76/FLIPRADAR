import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthProvider";
import {
  getStoredAccessToken,
  getStoredRefreshToken,
} from "../services/apiClient";
import type { CurrentUser } from "../types";

const serviceMocks = vi.hoisted(() => ({
  logout: vi.fn(),
  me: vi.fn(),
}));

vi.mock("../services/apiClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/apiClient")>();
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      auth: {
        ...actual.apiClient.auth,
        logout: serviceMocks.logout,
      },
      users: {
        ...actual.apiClient.users,
        me: serviceMocks.me,
      },
    },
  };
});

const currentUser: CurrentUser = {
  created_at: "2026-07-25T10:00:00Z",
  deletion_requested_at: null,
  deletion_scheduled_at: null,
  display_name: "Collector",
  email: "collector@example.com",
  id: "user-id",
  is_email_verified: true,
  pending_email: null,
  updated_at: "2026-07-25T10:00:00Z",
  username: "collector",
};

function AuthProbe() {
  const auth = useAuth();
  return (
    <div>
      <div>{auth.isLoadingUser ? "loading" : "settled"}</div>
      <div>{auth.isAuthenticated ? "authenticated" : "anonymous"}</div>
      <div>{auth.user?.username ?? "no-user"}</div>
      <button
        onClick={() =>
          auth.login({
            access_token: "new-access-token",
            refresh_token: "new-refresh-token",
            user: currentUser,
          })
        }
        type="button"
      >
        Login
      </button>
    </div>
  );
}

function renderAuthProbe() {
  render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      clear: vi.fn(() => storage.clear()),
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("starts anonymous when no access token is stored", async () => {
    renderAuthProbe();

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(screen.getByText("settled")).toBeInTheDocument();
    expect(serviceMocks.me).not.toHaveBeenCalled();
  });

  it("loads the current user when a stored token exists", async () => {
    localStorage.setItem("flipradar_token", "stored-access-token");
    serviceMocks.me.mockResolvedValue(currentUser);

    renderAuthProbe();

    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(await screen.findByText("collector")).toBeInTheDocument();
    expect(screen.getByText("authenticated")).toBeInTheDocument();
  });

  it("stores tokens and user state on login", async () => {
    const user = userEvent.setup();
    renderAuthProbe();

    await user.click(await screen.findByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByText("authenticated")).toBeInTheDocument();
    });
    expect(screen.getByText("collector")).toBeInTheDocument();
    expect(getStoredAccessToken()).toBe("new-access-token");
    expect(getStoredRefreshToken()).toBe("new-refresh-token");
  });
});
