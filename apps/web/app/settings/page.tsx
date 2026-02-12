"use client";

import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";

const NOTIFICATION_PREF_KEY = "poverlay.notifications.enabled";

export default function SettingsPage() {
  const { account, updateProfileMetadata, sendPasswordReset } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [photoURL, setPhotoURL] = useState("");
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isSendingReset, setIsSendingReset] = useState(false);

  useEffect(() => {
    setDisplayName(account?.displayName ?? "");
    setPhotoURL(account?.photoURL ?? "");
  }, [account?.displayName, account?.photoURL]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(NOTIFICATION_PREF_KEY);
    if (stored === "false") {
      setNotificationsEnabled(false);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(NOTIFICATION_PREF_KEY, notificationsEnabled ? "true" : "false");
  }, [notificationsEnabled]);

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
            Toggle whether render completion notifications are enabled for your account profile scaffold.
          </p>
          <label className="mt-4 inline-flex items-center gap-3">
            <input
              type="checkbox"
              checked={notificationsEnabled}
              onChange={(event) => setNotificationsEnabled(event.target.checked)}
              className="h-4 w-4 rounded border-[var(--color-border)]"
            />
            <span className="text-sm font-medium">
              {notificationsEnabled ? "Notifications enabled" : "Notifications opt-out enabled"}
            </span>
          </label>
          <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
            This preference is currently scaffolded locally and will be persisted to backend user settings in a follow-up.
          </p>
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
