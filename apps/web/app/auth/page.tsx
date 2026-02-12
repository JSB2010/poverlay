"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { AUTH_METHODS } from "@/lib/auth/methods";

type AuthMode = "sign-in" | "sign-up" | "reset";

function normalizedMode(value: string | null): AuthMode {
  if (value === "sign-up" || value === "reset") {
    return value;
  }
  return "sign-in";
}

export default function AuthPage() {
  const { isEnabled, isLoading, account, signInWithPassword, signUpWithPassword, sendPasswordReset } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const nextPath = useMemo(() => {
    const raw = searchParams.get("next");
    if (!raw || !raw.startsWith("/")) {
      return "/studio";
    }
    return raw;
  }, [searchParams]);

  const [mode, setMode] = useState<AuthMode>(() => normalizedMode(searchParams.get("mode")));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setMode(normalizedMode(searchParams.get("mode")));
  }, [searchParams]);

  useEffect(() => {
    if (!isLoading && account) {
      router.replace(nextPath);
    }
  }, [account, isLoading, nextPath, router]);

  async function handleCredentialSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    if (!password) {
      setError("Password is required.");
      return;
    }

    if (mode === "sign-up" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "sign-up") {
        await signUpWithPassword(email.trim(), password);
      } else {
        await signInWithPassword(email.trim(), password);
      }
      router.replace(nextPath);
    } catch (submissionError) {
      const message = submissionError instanceof Error ? submissionError.message : "Authentication failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim()) {
      setError("Enter your account email to receive a reset link.");
      return;
    }

    setIsSubmitting(true);
    try {
      await sendPasswordReset(email.trim());
      setSuccess("Password reset email sent. Check your inbox for the secure link.");
    } catch (resetError) {
      const message = resetError instanceof Error ? resetError.message : "Could not send reset email.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isEnabled) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-8">
          <h1 className="text-2xl font-semibold">Authentication is disabled</h1>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
            Set `NEXT_PUBLIC_FIREBASE_AUTH_ENABLED=true` and Firebase web credentials in `.env` to enable sign-in.
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white no-underline"
          >
            Back to landing
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-primary)]">Account</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Sign in to continue</h1>
        <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
          Studio, Media, and Settings are available only for signed-in users.
        </p>

        <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)]/20 p-4 text-sm text-[var(--color-muted-foreground)]">
          Renders keep running in the background after submission. You can close this page and sign back in later to
          track progress and download outputs.
        </div>

        <div className="mt-6 grid gap-2 sm:grid-cols-3">
          <button
            type="button"
            onClick={() => setMode("sign-in")}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${mode === "sign-in" ? "bg-[var(--color-primary)] text-white" : "border border-[var(--color-border)]"}`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => setMode("sign-up")}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${mode === "sign-up" ? "bg-[var(--color-primary)] text-white" : "border border-[var(--color-border)]"}`}
          >
            Create account
          </button>
          <button
            type="button"
            onClick={() => setMode("reset")}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${mode === "reset" ? "bg-[var(--color-primary)] text-white" : "border border-[var(--color-border)]"}`}
          >
            Reset password
          </button>
        </div>

        <div className="mt-6 space-y-3">
          {AUTH_METHODS.map((method) => (
            <div key={method.id} className="rounded-lg border border-[var(--color-border)] p-3">
              <p className="text-sm font-medium">
                {method.label} {method.enabled ? "" : "(coming soon)"}
              </p>
              <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{method.description}</p>
            </div>
          ))}
        </div>

        <form onSubmit={mode === "reset" ? handleResetPassword : handleCredentialSubmit} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
              required
            />
          </label>

          {mode !== "reset" && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
                className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                required
              />
            </label>
          )}

          {mode === "sign-up" && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Confirm password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                required
              />
            </label>
          )}

          {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-600">{error}</p>}
          {success && (
            <p className="rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-700">
              {success}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-[var(--color-primary)] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? "Please wait..."
              : mode === "sign-up"
                ? "Create account"
                : mode === "reset"
                  ? "Send reset email"
                  : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
