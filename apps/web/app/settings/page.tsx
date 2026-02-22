"use client";

import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiUrl } from "@/lib/api-base";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

const CONFIGURED_API_BASE = PUBLIC_WEB_CONFIG.apiBase;

type UserSettingsResponse = {
  notifications_enabled?: boolean;
};

function buildApiUrl(path: string): string {
  return apiUrl(path, CONFIGURED_API_BASE);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readApiPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (isRecord(payload) && typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }
  return fallback;
}

export default function SettingsPage() {
  const { account, getIdToken, updateProfileMetadata, sendPasswordReset } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [photoURL, setPhotoURL] = useState("");
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [notificationMessage, setNotificationMessage] = useState<string | null>(null);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingNotifications, setIsLoadingNotifications] = useState(true);
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);
  const [isSendingReset, setIsSendingReset] = useState(false);

  useEffect(() => {
    setDisplayName(account?.displayName ?? "");
    setPhotoURL(account?.photoURL ?? "");
  }, [account?.displayName, account?.photoURL]);

  useEffect(() => {
    if (!account?.uid) {
      setIsLoadingNotifications(false);
      return;
    }

    let isMounted = true;
    async function loadNotificationPreference(): Promise<void> {
      setNotificationError(null);
      setNotificationMessage(null);
      setIsLoadingNotifications(true);
      try {
        const token = await getIdToken();
        if (!token) {
          throw new Error("Authentication token unavailable.");
        }

        const response = await fetch(buildApiUrl("/api/user/settings"), {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          cache: "no-store",
        });
        const payload = (await readApiPayload(response)) as UserSettingsResponse | null;
        if (!response.ok) {
          throw new Error(extractErrorMessage(payload, "Could not load notification preference."));
        }

        if (isMounted && typeof payload?.notifications_enabled === "boolean") {
          setNotificationsEnabled(payload.notifications_enabled);
        }
      } catch (error) {
        if (isMounted) {
          const message = error instanceof Error ? error.message : "Could not load notification preference.";
          setNotificationError(message);
        }
      } finally {
        if (isMounted) {
          setIsLoadingNotifications(false);
        }
      }
    }

    void loadNotificationPreference();
    return () => {
      isMounted = false;
    };
  }, [account?.uid, getIdToken]);

  async function handleNotificationsToggle(nextValue: boolean): Promise<void> {
    const previous = notificationsEnabled;
    setNotificationsEnabled(nextValue);
    setNotificationError(null);
    setNotificationMessage(null);
    setIsSavingNotifications(true);
    try {
      const token = await getIdToken();
      if (!token) {
        throw new Error("Authentication token unavailable.");
      }

      const response = await fetch(buildApiUrl("/api/user/settings"), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ notifications_enabled: nextValue }),
      });
      const payload = (await readApiPayload(response)) as UserSettingsResponse | null;
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Could not update notification preference."));
      }

      const serverValue = typeof payload?.notifications_enabled === "boolean" ? payload.notifications_enabled : nextValue;
      setNotificationsEnabled(serverValue);
      setNotificationMessage(serverValue ? "Completion emails are enabled." : "Completion emails are disabled.");
    } catch (error) {
      setNotificationsEnabled(previous);
      const message = error instanceof Error ? error.message : "Could not update notification preference.";
      setNotificationError(message);
    } finally {
      setIsSavingNotifications(false);
    }
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileError(null);
    setProfileMessage(null);
    setIsSaving(true);
    try {
      await updateProfileMetadata({ displayName, photoURL });
      setProfileMessage("Profile metadata saved.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not update profile.";
      setProfileError(message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSendResetEmail(): Promise<void> {
    if (!account?.email) {
      setPasswordMessage("Account email unavailable for password reset.");
      return;
    }
    setPasswordMessage(null);
    setIsSendingReset(true);
    try {
      await sendPasswordReset(account.email);
      setPasswordMessage("Password reset/change email sent.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not send password reset.";
      setPasswordMessage(message);
    } finally {
      setIsSendingReset(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight">Account Settings</h1>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
        Update profile metadata, notification preferences, and password access.
      </p>

      <div className="mt-8 grid gap-6">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-lg font-semibold">Profile metadata</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            Current account: {account?.email ?? "unknown"}
          </p>

          <form onSubmit={handleSaveProfile} className="mt-5 space-y-4">
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Display name</span>
              <input
                type="text"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                placeholder="Rider name"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-medium">Profile image URL</span>
              <input
                type="url"
                value={photoURL}
                onChange={(event) => setPhotoURL(event.target.value)}
                className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                placeholder="https://example.com/avatar.jpg"
              />
            </label>

            {profileError && (
              <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-600">{profileError}</p>
            )}
            {profileMessage && (
              <p className="rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-700">
                {profileMessage}
              </p>
            )}

            <button
              type="submit"
              disabled={isSaving}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSaving ? "Saving..." : "Save profile"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            Toggle whether render completion emails are enabled for your account.
          </p>
          <label className="mt-4 inline-flex items-center gap-3">
            <input
              type="checkbox"
              checked={notificationsEnabled}
              disabled={isLoadingNotifications || isSavingNotifications}
              onChange={(event) => void handleNotificationsToggle(event.target.checked)}
              className="h-4 w-4 rounded border-[var(--color-border)]"
            />
            <span className="text-sm font-medium">
              {notificationsEnabled ? "Notifications enabled" : "Notifications opt-out enabled"}
            </span>
          </label>
          {isLoadingNotifications && <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">Loading preference...</p>}
          {notificationError && <p className="mt-2 text-xs text-red-600">{notificationError}</p>}
          {notificationMessage && <p className="mt-2 text-xs text-green-700">{notificationMessage}</p>}
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-lg font-semibold">Password reset / change</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            Send a secure reset link to {account?.email ?? "your account email"}.
          </p>
          {passwordMessage && (
            <p className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm">
              {passwordMessage}
            </p>
          )}
          <button
            type="button"
            onClick={() => void handleSendResetEmail()}
            disabled={isSendingReset}
            className="mt-4 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)]/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSendingReset ? "Sending..." : "Email password reset link"}
          </button>
        </section>
      </div>
    </main>
  );
}
