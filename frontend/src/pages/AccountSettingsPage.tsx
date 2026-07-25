import { KeyRound, Mail, Save, UserRound } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { api, getApiError } from "../api/client";
import type { CurrentUser } from "../types";

export function AccountSettingsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [isLoadingPassword, setIsLoadingPassword] = useState(false);
  const [isLoadingEmail, setIsLoadingEmail] = useState(false);

  useEffect(() => {
    api.get<CurrentUser>("/users/me").then((response) => {
      setUser(response.data);
      setDisplayName(response.data.display_name ?? response.data.username);
      setNewEmail(response.data.pending_email ?? "");
    });
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoadingProfile(true);
    setProfileMessage("");
    try {
      const response = await api.patch<CurrentUser>("/users/me", {
        display_name: displayName,
      });
      setUser(response.data);
      setDisplayName(response.data.display_name ?? response.data.username);
      setProfileMessage("Display name updated.");
    } catch (error) {
      setProfileMessage(getApiError(error));
    } finally {
      setIsLoadingProfile(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoadingPassword(true);
    setPasswordMessage("");
    try {
      const response = await api.post("/users/me/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordMessage(response.data.message);
    } catch (error) {
      setPasswordMessage(getApiError(error));
    } finally {
      setIsLoadingPassword(false);
    }
  }

  async function requestEmailChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoadingEmail(true);
    setEmailMessage("");
    try {
      const response = await api.post("/users/me/email-change/request", {
        new_email: newEmail,
        current_password: emailPassword,
      });
      const profile = await api.get<CurrentUser>("/users/me");
      setUser(profile.data);
      setEmailPassword("");
      setEmailMessage(response.data.message);
    } catch (error) {
      setEmailMessage(getApiError(error));
    } finally {
      setIsLoadingEmail(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="metric-label">Account</p>
          <h1 className="mt-2 text-3xl font-bold text-white">Settings</h1>
        </div>
        {user ? (
          <div className="rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm text-blue-100">
            Signed in as <span className="font-semibold">{user.username}</span>
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <form className="page-card space-y-5" onSubmit={saveProfile}>
          <div className="flex items-center gap-3">
            <UserRound className="text-blue-700" size={20} aria-hidden="true" />
            <h2 className="text-lg font-bold text-slate-950">Profile</h2>
          </div>
          <label className="block space-y-2">
            <span className="field-label">Display name</span>
            <input
              className="field-input"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
            />
          </label>
          {profileMessage ? (
            <p className="text-sm font-medium text-slate-600">
              {profileMessage}
            </p>
          ) : null}
          <button
            className="primary-button w-full"
            type="submit"
            disabled={isLoadingProfile || !user}
          >
            <Save size={17} aria-hidden="true" />
            {isLoadingProfile ? "Saving..." : "Save profile"}
          </button>
        </form>

        <form className="page-card space-y-5" onSubmit={changePassword}>
          <div className="flex items-center gap-3">
            <KeyRound className="text-blue-700" size={20} aria-hidden="true" />
            <h2 className="text-lg font-bold text-slate-950">Password</h2>
          </div>
          <label className="block space-y-2">
            <span className="field-label">Current password</span>
            <input
              className="field-input"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          <label className="block space-y-2">
            <span className="field-label">New password</span>
            <input
              className="field-input"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
            />
          </label>
          {passwordMessage ? (
            <p className="text-sm font-medium text-slate-600">
              {passwordMessage}
            </p>
          ) : null}
          <button
            className="primary-button w-full"
            type="submit"
            disabled={isLoadingPassword}
          >
            <KeyRound size={17} aria-hidden="true" />
            {isLoadingPassword ? "Changing..." : "Change password"}
          </button>
        </form>

        <form className="page-card space-y-5" onSubmit={requestEmailChange}>
          <div className="flex items-center gap-3">
            <Mail className="text-blue-700" size={20} aria-hidden="true" />
            <h2 className="text-lg font-bold text-slate-950">Email</h2>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            Current email
            <div className="font-semibold text-slate-950">
              {user?.email ?? ""}
            </div>
          </div>
          {user?.pending_email ? (
            <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-950">
              Pending confirmation
              <div className="font-semibold">{user.pending_email}</div>
            </div>
          ) : null}
          <label className="block space-y-2">
            <span className="field-label">New email</span>
            <input
              className="field-input"
              type="email"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="block space-y-2">
            <span className="field-label">Current password</span>
            <input
              className="field-input"
              type="password"
              value={emailPassword}
              onChange={(event) => setEmailPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {emailMessage ? (
            <p className="text-sm font-medium text-slate-600">{emailMessage}</p>
          ) : null}
          <button
            className="primary-button w-full"
            type="submit"
            disabled={isLoadingEmail || !user}
          >
            <Mail size={17} aria-hidden="true" />
            {isLoadingEmail ? "Sending..." : "Send confirmation"}
          </button>
        </form>
      </div>
    </section>
  );
}
