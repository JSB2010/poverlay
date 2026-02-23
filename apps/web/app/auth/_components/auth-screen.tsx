"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

type AuthMode = "login" | "register" | "reset";

type AuthScreenProps = {
  mode: AuthMode;
};

type AuthContent = {
  eyebrow: string;
  title: string;
  description: string;
  submitLabel: string;
};

const MODE_CONTENT: Record<AuthMode, AuthContent> = {
  login: {
    eyebrow: "Welcome back",
    title: "Sign in to your workspace",
    description: "Access Studio, Media, and account controls.",
    submitLabel: "Sign in",
  },
  register: {
    eyebrow: "Create account",
    title: "Start rendering with POVerlay",
    description: "Set up your account to save jobs, track progress, and manage exports.",
    submitLabel: "Create account",
  },
  reset: {
    eyebrow: "Password reset",
    title: "Send a secure reset link",
    description: "We will email you a link to update your password.",
    submitLabel: "Send reset link",
  },
};

function sanitizeNextPath(value: string | null): string {
  if (!value || !value.startsWith("/")) {
    return "/studio";
  }
  return value;
}

export function AuthScreen({ mode }: AuthScreenProps) {
  const { isEnabled, isLoading, account, signInWithPassword, signUpWithPassword, sendPasswordReset } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const content = MODE_CONTENT[mode];
  const nextPath = useMemo(() => sanitizeNextPath(searchParams.get("next")), [searchParams]);
  const nextQuery = useMemo(() => `?next=${encodeURIComponent(nextPath)}`, [nextPath]);

  useEffect(() => {
    if (!isLoading && account) {
      router.replace(nextPath);
    }
  }, [account, isLoading, nextPath, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    if (mode !== "reset" && !password) {
      setError("Password is required.");
      return;
    }

    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "reset") {
        await sendPasswordReset(email.trim());
        setSuccess("Password reset email sent. Check your inbox for the secure link.");
        return;
      }

      if (mode === "register") {
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

  if (!isEnabled) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
          <h1 className="text-2xl font-semibold">Authentication is disabled</h1>
          <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
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
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <section className="grid overflow-hidden rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-xl shadow-[var(--color-primary)]/5 lg:grid-cols-[1.08fr_1fr]">
        <div className="relative overflow-hidden border-b border-[var(--color-border)] bg-gradient-to-br from-[var(--color-primary)]/14 via-cyan-500/10 to-transparent p-8 lg:border-b-0 lg:border-r lg:p-10">
          <div className="absolute -left-12 -top-24 h-52 w-52 rounded-full bg-[var(--color-primary)]/25 blur-3xl" />
          <div className="absolute -right-20 bottom-8 h-44 w-44 rounded-full bg-cyan-400/20 blur-3xl" />
          <div className="relative z-10 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">POVerlay account</p>
            <h1 className="max-w-sm text-3xl font-bold tracking-tight">{content.title}</h1>
            <p className="max-w-sm text-sm text-[var(--color-muted-foreground)]">{content.description}</p>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/80 p-4 text-sm text-[var(--color-muted-foreground)]">
              Render jobs continue on the server after upload. You can sign back in later to monitor progress or download outputs.
            </div>
            <ul className="space-y-2 text-sm">
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)]/70 px-3 py-2">
                Secure email + password auth
              </li>
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)]/70 px-3 py-2">
                Access to Studio, Media, and Settings
              </li>
            </ul>
          </div>
        </div>

        <div className="p-8 lg:p-10">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">{content.eyebrow}</p>
          <p className="mt-4 text-sm text-[var(--color-muted-foreground)]">
            {mode === "login" && (
              <>
                New here?{" "}
                <Link href={`/auth/register${nextQuery}`} className="font-semibold text-[var(--color-primary)] no-underline hover:underline">
                  Create an account
                </Link>
              </>
            )}
            {mode === "register" && (
              <>
                Already have an account?{" "}
                <Link href={`/auth/login${nextQuery}`} className="font-semibold text-[var(--color-primary)] no-underline hover:underline">
                  Sign in
                </Link>
              </>
            )}
            {mode === "reset" && (
              <>
                Remembered your password?{" "}
                <Link href={`/auth/login${nextQuery}`} className="font-semibold text-[var(--color-primary)] no-underline hover:underline">
                  Return to sign in
                </Link>
              </>
            )}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3.5 py-2.5 text-sm outline-none transition-shadow focus:border-[var(--color-primary)] focus:ring-4 focus:ring-[var(--color-primary)]/15"
                required
              />
            </label>

            {mode !== "reset" && (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium">Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3.5 py-2.5 text-sm outline-none transition-shadow focus:border-[var(--color-primary)] focus:ring-4 focus:ring-[var(--color-primary)]/15"
                  required
                />
              </label>
            )}

            {mode === "register" && (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium">Confirm password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3.5 py-2.5 text-sm outline-none transition-shadow focus:border-[var(--color-primary)] focus:ring-4 focus:ring-[var(--color-primary)]/15"
                  required
                />
              </label>
            )}

            {mode === "login" && (
              <p className="text-right text-sm">
                <Link href={`/auth/reset${nextQuery}`} className="font-medium text-[var(--color-primary)] no-underline hover:underline">
                  Forgot password?
                </Link>
              </p>
            )}

            {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-600">{error}</p>}
            {success && (
              <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
                {success}
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-[var(--color-primary)]/20 transition-colors hover:bg-[var(--color-primary)]/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Please wait..." : content.submitLabel}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}

export function AuthScreenFallback() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
        <p className="text-sm text-[var(--color-muted-foreground)]">Loading authentication…</p>
      </section>
    </main>
  );
}
