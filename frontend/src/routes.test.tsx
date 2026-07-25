import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "./routes";

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  isLoadingUser: false,
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
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    user: authState.user,
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
      screen.getByText("Collector valuation workspace"),
    ).toBeInTheDocument();
  });
});
