"use client";

import Link from "next/link";
import { ArrowLeft, Home } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4">
      <div className="text-center">
        <h1 className="mb-4 text-6xl font-bold text-[var(--color-primary)]">404</h1>
        <h2 className="mb-2 text-2xl font-semibold">Page Not Found</h2>
        <p className="mb-8 text-[var(--color-muted-foreground)]">
          Sorry, we couldn't find the page you're looking for.
        </p>
        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-primary)] px-6 py-2.5 text-sm font-semibold text-white no-underline transition-all hover:-translate-y-0.5 hover:shadow-lg"
          >
            <Home className="h-4 w-4" />
            Go Home
          </Link>
          <button
            type="button"
            onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] px-6 py-2.5 text-sm font-medium no-underline transition-all hover:-translate-y-0.5 hover:bg-[var(--color-card)]/80"
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </button>
        </div>
      </div>
    </main>
  );
}

