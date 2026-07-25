import {
  KeyRound,
  Mail,
  Save,
  ShieldAlert,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearAuthSession, getApiError } from "../api/client";
import type { CurrentUser, RefreshSession } from "../types";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [sessions, setSessions] = useState<RefreshSession[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [sessionMessage, setSessionMessage] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [isLoadingPassword, setIsLoadingPassword] = useState(false);
  const [isLoadingEmail, setIsLoadingEmail] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

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

  async function loadSessions() {
    setIsLoadingSessions(true);
    setSessionMessage("");
    try {
      const response = await api.get<RefreshSession[]>("/users/me/sessions");
      setSessions(response.data);
      setSessionMessage(
        response.data.length > 0 ? "" : "No active sessions found.",
      );
    } catch (error) {
      setSessionMessage(getApiError(error));
    } finally {
      setIsLoadingSessions(false);
    }
  }

  async function revokeSession(sessionId: string) {
    setSessionMessage("");
    try {
      const response = await api.delete(`/users/me/sessions/${sessionId}`);
      setSessionMessage(response.data.message);
      await loadSessions();
    } catch (error) {
      setSessionMessage(getApiError(error));
    }
  }

  async function revokeAllSessions() {
    setIsLoadingSessions(true);
    setSessionMessage("");
    try {
      await api.delete("/users/me/sessions");
      clearAuthSession();
      navigate("/login");
    } catch (error) {
      setSessionMessage(getApiError(error));
      setIsLoadingSessions(false);
    }
  }

  async function requestAccountDeletion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsDeletingAccount(true);
    setDeleteMessage("");
    try {
      const response = await api.post("/users/me/deletion-request", {
        current_password: deletePassword,
      });
      const scheduledAt = formatSessionDate(
        response.data.deletion_scheduled_at,
      );
      setDeletePassword("");
      setDeleteMessage(
        `${response.data.message} Scheduled for ${scheduledAt}.`,
      );
      const profile = await api.get<CurrentUser>("/users/me");
      setUser(profile.data);
    } catch (error) {
      setDeleteMessage(getApiError(error));
    } finally {
      setIsDeletingAccount(false);
    }
  }

  function formatSessionDate(value: string | null) {
    if (!value) {
      return "Not seen yet";
    }
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
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

      <section className="page-card space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <ShieldCheck
              className="text-blue-700"
              size={20}
              aria-hidden="true"
            />
            <h2 className="text-lg font-bold text-slate-950">
              Active sessions
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="secondary-button"
              type="button"
              onClick={loadSessions}
              disabled={isLoadingSessions}
            >
              <ShieldCheck size={17} aria-hidden="true" />
              {isLoadingSessions
                ? "Loading..."
                : "Display recent active sessions"}
            </button>
            <button
              className="secondary-button border-red-200 text-red-700 hover:bg-red-50"
              type="button"
              onClick={revokeAllSessions}
              disabled={isLoadingSessions}
            >
              <X size={17} aria-hidden="true" />
              End all sessions
            </button>
          </div>
        </div>
        {sessionMessage ? (
          <p className="text-sm font-medium text-slate-600">{sessionMessage}</p>
        ) : null}
        {sessions.length > 0 ? (
          <div className="divide-y divide-slate-200 rounded-md border border-slate-200">
            {sessions.map((session) => (
              <div
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                key={session.id}
              >
                <div className="text-sm">
                  <p className="font-semibold text-slate-950">
                    Last active {formatSessionDate(session.last_seen_at)}
                  </p>
                  <p className="mt-1 text-slate-500">
                    Created {formatSessionDate(session.created_at)} · Expires{" "}
                    {formatSessionDate(session.expires_at)}
                  </p>
                </div>
                <button
                  className="secondary-button border-red-200 text-red-700 hover:bg-red-50"
                  type="button"
                  onClick={() => void revokeSession(session.id)}
                >
                  <X size={17} aria-hidden="true" />
                  Revoke
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-red-200 bg-white p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <ShieldAlert className="text-red-700" size={20} aria-hidden="true" />
          <h2 className="text-lg font-bold text-slate-950">Danger zone</h2>
        </div>
        <form
          className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto]"
          onSubmit={requestAccountDeletion}
        >
          <label className="block space-y-2">
            <span className="field-label">Confirm password</span>
            <input
              className="field-input"
              type="password"
              value={deletePassword}
              onChange={(event) => setDeletePassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          <button
            className="primary-button self-end bg-red-700 hover:bg-red-800"
            type="submit"
            disabled={isDeletingAccount || !user}
          >
            <ShieldAlert size={17} aria-hidden="true" />
            {isDeletingAccount ? "Confirming..." : "Delete account"}
          </button>
        </form>
        {user?.deletion_scheduled_at ? (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-950">
            Account deletion scheduled for{" "}
            {formatSessionDate(user.deletion_scheduled_at)}.
          </p>
        ) : null}
        {deleteMessage ? (
          <p className="mt-4 text-sm font-medium text-slate-600">
            {deleteMessage}
          </p>
        ) : null}
      </section>
    </section>
  );
}
