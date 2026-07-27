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
import { apiClient, getApiError } from "../../services/apiClient";
import { useAuth } from "../../auth/AuthProvider";
import type { CurrentUser, RefreshSession } from "../../types";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const auth = useAuth();
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
    apiClient.users.me().then((response) => {
      setUser(response);
      setDisplayName(response.display_name ?? response.username);
      setNewEmail(response.pending_email ?? "");
    });
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoadingProfile(true);
    setProfileMessage("");
    try {
      const response = await apiClient.users.updateMe({
        display_name: displayName,
      });
      setUser(response);
      setDisplayName(response.display_name ?? response.username);
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
      const response = await apiClient.users.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordMessage(response.message);
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
      const response = await apiClient.users.requestEmailChange({
        new_email: newEmail,
        current_password: emailPassword,
      });
      const profile = await apiClient.users.me();
      setUser(profile);
      setEmailPassword("");
      setEmailMessage(response.message);
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
      const response = await apiClient.users.listSessions();
      setSessions(response);
      setSessionMessage(response.length > 0 ? "" : "No active sessions found.");
    } catch (error) {
      setSessionMessage(getApiError(error));
    } finally {
      setIsLoadingSessions(false);
    }
  }

  async function revokeSession(sessionId: string) {
    setSessionMessage("");
    try {
      const response = await apiClient.users.revokeSession(sessionId);
      setSessionMessage(response.message);
      await loadSessions();
    } catch (error) {
      setSessionMessage(getApiError(error));
    }
  }

  async function revokeAllSessions() {
    setIsLoadingSessions(true);
    setSessionMessage("");
    try {
      await apiClient.users.revokeAllSessions();
      await auth.logout();
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
      const response = await apiClient.users.requestDeletion(deletePassword);
      const scheduledAt = formatSessionDate(response.deletion_scheduled_at);
      setDeletePassword("");
      setDeleteMessage(`${response.message} Scheduled for ${scheduledAt}.`);
      const profile = await apiClient.users.me();
      setUser(profile);
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
      {user ? (
        <div className="inline-flex rounded-[var(--radius-control)] border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
          Signed in as{" "}
          <span className="ml-1 font-semibold text-[var(--color-text)]">
            {user.username}
          </span>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <form className="page-card space-y-5" onSubmit={saveProfile}>
          <div className="flex items-center gap-3">
            <UserRound
              className="text-[var(--color-info)]"
              size={20}
              aria-hidden="true"
            />
            <h2 className="text-lg font-bold text-[var(--color-text)]">
              Profile
            </h2>
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
            <p className="text-sm font-medium text-[var(--color-text-muted)]">
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
            <KeyRound
              className="text-[var(--color-info)]"
              size={20}
              aria-hidden="true"
            />
            <h2 className="text-lg font-bold text-[var(--color-text)]">
              Password
            </h2>
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
            <p className="text-sm font-medium text-[var(--color-text-muted)]">
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
            <Mail
              className="text-[var(--color-info)]"
              size={20}
              aria-hidden="true"
            />
            <h2 className="text-lg font-bold text-[var(--color-text)]">
              Email
            </h2>
          </div>
          <div className="rounded-[var(--radius-control)] border border-[var(--color-border-soft)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
            Current email
            <div className="font-semibold text-[var(--color-text)]">
              {user?.email ?? ""}
            </div>
          </div>
          {user?.pending_email ? (
            <div className="rounded-[var(--radius-control)] border border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] px-3 py-2 text-sm text-[var(--color-info)]">
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
            <p className="text-sm font-medium text-[var(--color-text-muted)]">
              {emailMessage}
            </p>
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
              className="text-[var(--color-info)]"
              size={20}
              aria-hidden="true"
            />
            <h2 className="text-lg font-bold text-[var(--color-text)]">
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
              className="secondary-button border-[var(--color-warning)] text-[var(--color-warning)] hover:bg-[rgba(145,3,3,0.1)]"
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
          <p className="text-sm font-medium text-[var(--color-text-muted)]">
            {sessionMessage}
          </p>
        ) : null}
        {sessions.length > 0 ? (
          <div className="divide-y divide-[var(--color-border-soft)] rounded-[var(--radius-control)] border border-[var(--color-border-soft)]">
            {sessions.map((session) => (
              <div
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                key={session.id}
              >
                <div className="text-sm">
                  <p className="font-semibold text-[var(--color-text)]">
                    Last active {formatSessionDate(session.last_seen_at)}
                  </p>
                  <p className="mt-1 text-[var(--color-text-muted)]">
                    Created {formatSessionDate(session.created_at)} · Expires{" "}
                    {formatSessionDate(session.expires_at)}
                  </p>
                </div>
                <button
                  className="secondary-button border-[var(--color-warning)] text-[var(--color-warning)] hover:bg-[rgba(145,3,3,0.1)]"
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

      <section className="rounded-[var(--radius-card)] border border-[var(--color-warning)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-soft)]">
        <div className="flex items-center gap-3">
          <ShieldAlert
            className="text-[var(--color-warning)]"
            size={20}
            aria-hidden="true"
          />
          <h2 className="text-lg font-bold text-[var(--color-text)]">
            Danger zone
          </h2>
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
            className="primary-button self-end bg-[var(--color-warning)] text-white hover:brightness-110"
            type="submit"
            disabled={isDeletingAccount || !user}
          >
            <ShieldAlert size={17} aria-hidden="true" />
            {isDeletingAccount ? "Confirming..." : "Delete account"}
          </button>
        </form>
        {user?.deletion_scheduled_at ? (
          <p className="mt-4 rounded-[var(--radius-control)] border border-[var(--color-warning)] bg-[rgba(145,3,3,0.1)] px-3 py-2 text-sm font-medium text-[var(--color-loss)]">
            Account deletion scheduled for{" "}
            {formatSessionDate(user.deletion_scheduled_at)}.
          </p>
        ) : null}
        {deleteMessage ? (
          <p className="mt-4 text-sm font-medium text-[var(--color-text-muted)]">
            {deleteMessage}
          </p>
        ) : null}
      </section>
    </section>
  );
}
