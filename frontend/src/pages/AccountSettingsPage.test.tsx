import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { AccountSettingsPage } from "./AccountSettingsPage";

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  clearAuthSession: vi.fn(),
  getApiError: () => "Request failed",
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
    vi.mocked(api.get).mockResolvedValue({ data: userProfile });
    vi.mocked(api.post).mockResolvedValue({
      data: {
        message:
          "Account deletion confirmed. Your user data is scheduled for removal in 24 hours.",
        deletion_scheduled_at: "2026-07-26T10:00:00Z",
      },
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

    expect(api.post).toHaveBeenCalledWith("/users/me/deletion-request", {
      current_password: "Str0ng!Pass",
    });
    expect(
      await screen.findByText(/scheduled for removal in 24 hours/i),
    ).toBeInTheDocument();
  });
});
