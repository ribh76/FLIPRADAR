import { CheckCheck, Mail } from "lucide-react";
import { useCallback } from "react";
import { useServerQuery } from "../../hooks/serverState";
import { apiClient } from "../../services/apiClient";
import type { AppNotification, NotificationPreference } from "../../types";
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
  const inbox = useServerQuery<AppNotification[]>(
    ["notifications"],
    useCallback(() => apiClient.notifications.list(), []),
  );
  const preferences = useServerQuery<NotificationPreference[]>(
    ["notification-preferences"],
    useCallback(() => apiClient.notifications.preferences(), []),
  );

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

  if (inbox.isLoading || preferences.isLoading)
    return <LoadingState title="Loading notifications..." />;
  if (inbox.error || preferences.error)
    return (
      <ErrorState
        title="Notifications unavailable"
        message={inbox.error || preferences.error}
        onRetry={() => {
          void inbox.refetch();
          void preferences.refetch();
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
              <button
                className={`w-full rounded-lg border p-4 text-left transition hover:border-[var(--color-accent)] ${notification.is_read ? "border-[var(--color-border-soft)]" : "border-[var(--color-accent)] bg-[rgba(73,252,226,0.08)]"}`}
                key={notification.id}
                onClick={() => void markRead(notification)}
                type="button"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-bold text-[var(--color-text)]">
                      {notification.title}
                    </p>
                    <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                      {notification.message}
                    </p>
                  </div>
                  <time className="shrink-0 text-xs text-[var(--color-text-muted)]">
                    {formatNotificationTime(notification.created_at)}
                  </time>
                </div>
              </button>
            ))
          )}
        </div>
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
