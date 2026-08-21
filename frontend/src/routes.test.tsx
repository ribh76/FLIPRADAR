import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "./routes";

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  isLoadingUser: false,
  isSessionExpired: false,
  user: null as null | {
    display_name: string | null;
    is_email_verified: boolean;
    username: string;
  },
}));

vi.mock("./auth/AuthProvider", () => ({
  useAuth: () => ({
    isAuthenticated: authState.isAuthenticated,
    isLoadingUser: authState.isLoadingUser,
    isSessionExpired: authState.isSessionExpired,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    user: authState.user,
  }),
}));

vi.mock("./theme/ThemeProvider", () => ({
  useTheme: () => ({
    theme: "dark",
    toggleTheme: vi.fn(),
  }),
}));

function renderRoute(path: string) {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [path],
  });
  render(<RouterProvider router={router} />);
  return router;
}

describe("routing authentication", () => {
  beforeEach(() => {
    authState.isAuthenticated = false;
    authState.isLoadingUser = false;
    authState.isSessionExpired = false;
    authState.user = null;
  });

  it("redirects protected routes to login when unauthenticated", async () => {
    renderRoute("/dashboard");

    expect(await screen.findByText("Sign in to FlipRadar")).toBeInTheDocument();
  });

  it("shows the auth loading state before protected routes resolve", () => {
    authState.isLoadingUser = true;

    renderRoute("/dashboard");

    expect(screen.getByText("Loading workspace...")).toBeInTheDocument();
  });

  it("explains when a protected route redirects after a session expires", async () => {
    authState.isSessionExpired = true;

    renderRoute("/watchlist");

    expect(
      await screen.findByText("Your session expired. Please sign in again."),
    ).toBeInTheDocument();
  });

  it("renders dedicated recovery pages for unauthorized and missing routes", async () => {
    renderRoute("/unauthorized");
    expect(
      await screen.findByRole("heading", {
        name: "You don’t have access to this page",
      }),
    ).toBeInTheDocument();

    renderRoute("/no-such-page");
    expect(
      await screen.findByRole("heading", { name: "Page not found" }),
    ).toBeInTheDocument();
  });

  it("renders password and MFA recovery entry points", async () => {
    renderRoute("/forgot-password");
    expect(
      await screen.findByRole("heading", { name: "Reset your password" }),
    ).toBeInTheDocument();

    renderRoute("/mfa-reset");
    expect(
      await screen.findByRole("heading", { name: "Reset MFA" }),
    ).toBeInTheDocument();
  });

  it("renders protected route content when authenticated", async () => {
    authState.isAuthenticated = true;
    authState.user = {
      display_name: "Collector",
      is_email_verified: true,
      username: "collector",
    };

    renderRoute("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Workspace overview and shortcuts."),
    ).toBeInTheDocument();
  });

  it("requires email verification before rendering protected routes", async () => {
    authState.isAuthenticated = true;
    authState.user = {
      display_name: "Collector",
      is_email_verified: false,
      username: "collector",
    };

    renderRoute("/dashboard");

    expect(
      await screen.findByText(
        "Check your inbox and open the verification link before using FlipRadar.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the authenticated portfolio analysis workflow route", async () => {
    authState.isAuthenticated = true;
    authState.user = {
      display_name: "Collector",
      is_email_verified: true,
      username: "collector",
    };

    renderRoute("/portfolio/analyze");

    expect(
      await screen.findByRole("heading", { name: "Analyze portfolio" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Analyze portfolio" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Collectibles-market disclaimer"),
    ).toBeInTheDocument();
  });
});
