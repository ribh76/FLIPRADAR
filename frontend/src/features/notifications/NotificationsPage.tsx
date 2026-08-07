import { CheckCheck, Mail } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import type { AppNotification, NotificationPreference } from "../../types";
import type { NotificationSettings } from "../../types";
import {
  Card,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../components/ui";

const typeLabels: Record<NotificationPreference["notification_type"], string> =
  {
    price_drop: "Price drops",
    target_reached: "Target price reached",
    ended_listing: "Ended listings",
    deal_score: "High deal scores",
  };

function formatNotificationTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function NotificationsPage() {
  const [quietHoursStart, setQuietHoursStart] = useState("");
  const [quietHoursEnd, setQuietHoursEnd] = useState("");
  const inbox = useServerQuery<AppNotification[]>(
    ["notifications"],
    useCallback(() => apiClient.notifications.list(), []),
  );
  const preferences = useServerQuery<NotificationPreference[]>(
    ["notification-preferences"],
    useCallback(() => apiClient.notifications.preferences(), []),
  );
  const settings = useServerQuery<NotificationSettings>(
    ["notification-settings"],
    useCallback(() => apiClient.notifications.settings(), []),
  );

  useEffect(() => {
    setQuietHoursStart(settings.data?.quiet_hours_start ?? "");
    setQuietHoursEnd(settings.data?.quiet_hours_end ?? "");
  }, [settings.data?.quiet_hours_end, settings.data?.quiet_hours_start]);

  async function markRead(notification: AppNotification) {
    if (notification.is_read) return;
    const updated = await apiClient.notifications.markRead(notification.id);
    inbox.setData(
      (inbox.data ?? []).map((entry) =>
        entry.id === updated.id ? updated : entry,
      ),
    );
  }

  async function markAllRead() {
    await apiClient.notifications.markAllRead();
    inbox.setData(
      (inbox.data ?? []).map((entry) => ({ ...entry, is_read: true })),
    );
  }

  async function setPreference(
    preference: NotificationPreference,
    key: "in_app_enabled" | "email_enabled",
  ) {
    const updated = await apiClient.notifications.updatePreference(
      preference.notification_type,
      { [key]: !preference[key] },
    );
    preferences.setData(
      (preferences.data ?? []).map((entry) =>
        entry.notification_type === updated.notification_type ? updated : entry,
      ),
    );
  }

  async function updateSettings(payload: Partial<NotificationSettings>) {
    const updated = await apiClient.notifications.updateSettings(payload);
    settings.setData(updated);
  }

  async function saveQuietHours() {
    if (!quietHoursStart && !quietHoursEnd) {
      await updateSettings({ quiet_hours_start: null, quiet_hours_end: null });
      return;
    }
    if (quietHoursStart && quietHoursEnd) {
      await updateSettings({
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
      });
    }
  }

  if (inbox.isLoading || preferences.isLoading || settings.isLoading)
    return <LoadingState title="Loading notifications..." />;
  if (inbox.error || preferences.error || settings.error)
    return (
      <ErrorState
        title="Notifications unavailable"
        message={inbox.error || preferences.error || settings.error}
        onRetry={() => {
          void inbox.refetch();
          void preferences.refetch();
          void settings.refetch();
        }}
      />
    );

  const unreadCount =
    inbox.data?.filter((notification) => !notification.is_read).length ?? 0;
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          action={
            unreadCount > 0 ? (
              <button
                className="secondary-button"
                onClick={() => void markAllRead()}
                type="button"
              >
                <CheckCheck size={16} /> Mark all read
              </button>
            ) : null
          }
        >
          <CardTitle>Notification inbox</CardTitle>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            {unreadCount
              ? `${unreadCount} unread watchlist update${unreadCount === 1 ? "" : "s"}.`
              : "You’re all caught up."}
          </p>
        </CardHeader>
        <div className="mt-4 space-y-3">
          {!inbox.data?.length ? (
            <EmptyState
              title="No notifications yet"
              message="Watchlist changes will appear here after the next refresh."
            />
          ) : (
            inbox.data.map((notification) => (
              <article
                className={`w-full rounded-lg border p-4 text-left transition hover:border-[var(--color-accent)] ${notification.is_read ? "border-[var(--color-border-soft)]" : "border-[var(--color-accent)] bg-[rgba(73,252,226,0.08)]"}`}
                key={notification.id}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-bold text-[var(--color-text)]">
                      {notification.title}
                    </p>
                    <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                      {notification.message}
                    </p>
                    <div className="mt-3 flex gap-3 text-sm font-semibold">
                      <a
                        className="text-[var(--color-accent)] hover:underline"
                        href={notification.action_url}
                        onClick={() => void markRead(notification)}
                      >
                        View item
                      </a>
                      {!notification.is_read ? (
                        <button
                          className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                          onClick={() => void markRead(notification)}
                          type="button"
                        >
                          Mark read
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <time className="shrink-0 text-xs text-[var(--color-text-muted)]">
                    {formatNotificationTime(notification.created_at)}
                  </time>
                </div>
              </article>
            ))
          )}
        </div>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Global email delivery</CardTitle>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Quiet hours defer digests until the selected window ends.
          </p>
        </CardHeader>
        {settings.data ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="inline-flex items-center gap-2 text-sm font-semibold">
              <input
                checked={settings.data.email_enabled}
                onChange={() =>
                  void updateSettings({
                    email_enabled: !settings.data?.email_enabled,
                  })
                }
                type="checkbox"
              />{" "}
              Email digests enabled
            </label>
            <label className="text-sm font-semibold">
              Timezone
              <input
                className="mt-1 w-full rounded border border-[var(--color-border-soft)] bg-transparent px-3 py-2"
                onBlur={(event) => {
                  if (event.target.value !== settings.data?.timezone)
                    void updateSettings({ timezone: event.target.value });
                }}
                defaultValue={settings.data.timezone}
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm font-semibold">
                Quiet start
                <input
                  className="mt-1 w-full rounded border border-[var(--color-border-soft)] bg-transparent px-3 py-2"
                  onChange={(event) => setQuietHoursStart(event.target.value)}
                  type="time"
                  value={quietHoursStart}
                />
              </label>
              <label className="text-sm font-semibold">
                Quiet end
                <input
                  className="mt-1 w-full rounded border border-[var(--color-border-soft)] bg-transparent px-3 py-2"
                  onChange={(event) => setQuietHoursEnd(event.target.value)}
                  type="time"
                  value={quietHoursEnd}
                />
              </label>
            </div>
            <button
              className="secondary-button self-end"
              onClick={() => void saveQuietHours()}
              type="button"
            >
              Save quiet hours
            </button>
            <button
              className="secondary-button self-end"
              onClick={() =>
                void apiClient.notifications
                  .unsubscribeEmail()
                  .then(settings.setData)
              }
              type="button"
            >
              Unsubscribe from all email
            </button>
          </div>
        ) : null}
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Delivery preferences</CardTitle>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Email updates are combined into one digest per hour.
          </p>
        </CardHeader>
        <div className="mt-4 divide-y divide-[var(--color-border-soft)]">
          {preferences.data?.map((preference) => (
            <div
              className="flex flex-wrap items-center justify-between gap-4 py-4"
              key={preference.notification_type}
            >
              <span className="font-semibold">
                {typeLabels[preference.notification_type]}
              </span>
              <div className="flex gap-4 text-sm">
                <label className="inline-flex items-center gap-2">
                  <input
                    checked={preference.in_app_enabled}
                    onChange={() =>
                      void setPreference(preference, "in_app_enabled")
                    }
                    type="checkbox"
                  />{" "}
                  In app
                </label>
                <label className="inline-flex items-center gap-2">
                  <input
                    checked={preference.email_enabled}
                    onChange={() =>
                      void setPreference(preference, "email_enabled")
                    }
                    type="checkbox"
                  />{" "}
                  <Mail size={15} /> Email
                </label>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
