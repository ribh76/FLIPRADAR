import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { AccountSettingsPage } from "./AccountSettingsPage";

vi.mock("../api/client", () => ({
  apiClient: {
    users: {
      me: vi.fn(),
      requestDeletion: vi.fn(),
    },
  },
  getApiError: () => "Request failed",
}));

vi.mock("../auth/AuthProvider", () => ({
  useAuth: () => ({
    logout: vi.fn(),
  }),
}));

const userProfile = {
  id: "user-id",
  username: "collector",
  display_name: "Collector",
  email: "collector@example.com",
  pending_email: null,
  is_email_verified: true,
  deletion_requested_at: null,
  deletion_scheduled_at: null,
  created_at: "2026-07-25T10:00:00Z",
  updated_at: "2026-07-25T10:00:00Z",
};

describe("AccountSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.users.me).mockResolvedValue(userProfile);
    vi.mocked(apiClient.users.requestDeletion).mockResolvedValue({
      message:
        "Account deletion confirmed. Your user data is scheduled for removal in 24 hours.",
      deletion_scheduled_at: "2026-07-26T10:00:00Z",
    });
  });

  it("requires re-authentication before requesting account deletion", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <AccountSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText("Danger zone");
    await user.type(
      screen.getAllByLabelText("Confirm password")[0],
      "Str0ng!Pass",
    );
    await user.click(screen.getByRole("button", { name: /delete account/i }));

    expect(apiClient.users.requestDeletion).toHaveBeenCalledWith("Str0ng!Pass");
    expect(
      await screen.findByText(/scheduled for removal in 24 hours/i),
    ).toBeInTheDocument();
  });
});
