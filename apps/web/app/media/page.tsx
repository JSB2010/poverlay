import Link from "next/link";

export default function MediaPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-primary)]">Media</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Render Library</h1>
        <p className="mt-3 max-w-2xl text-sm text-[var(--color-muted-foreground)]">
          This page is the account-scoped media management entry point. Render, downloads, and deletion controls are
          being expanded in the next task.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/studio"
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white no-underline"
          >
            Open Studio
          </Link>
          <Link
            href="/settings"
            className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-foreground no-underline"
          >
            Account settings
          </Link>
        </div>
      </section>
    </main>
  );
}
