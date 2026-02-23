"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./theme-toggle";
import { useAuth } from "@/components/auth-provider";

export function Navbar() {
  const { account, signOut } = useAuth();
  const pathname = usePathname();
  const initials = (account?.displayName ?? account?.email ?? "P").trim().charAt(0).toUpperCase();

  function navLinkClass(href: string): string {
    const isActive = pathname === href;
    return `hidden rounded-lg px-3.5 py-1.5 text-sm font-medium no-underline transition-colors sm:inline-flex ${
      isActive
        ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
        : "text-[var(--color-muted-foreground)] hover:text-foreground"
    }`;
  }

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-border/70 bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 text-foreground no-underline transition-opacity hover:opacity-85">
          <Image src="/logo.png" alt="POVerlay Logo" width={34} height={34} className="h-[34px] w-[34px] object-contain" priority />
          <span className="text-xl font-bold tracking-tight sm:text-2xl" style={{ fontFamily: "var(--font-display), system-ui, sans-serif" }}>
            POVerlay
          </span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link href="/studio" className={navLinkClass("/studio")}>
            Studio
          </Link>
          {account && (
            <>
              <Link href="/media" className={navLinkClass("/media")}>
                Media
              </Link>
              <Link href="/settings" className={navLinkClass("/settings")}>
                Settings
              </Link>
            </>
          )}
          {account && (
            <Link
              href="/settings"
              className="inline-flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-[var(--color-border)] bg-[var(--color-card)] text-sm font-semibold text-[var(--color-primary)] no-underline shadow-sm sm:hidden"
              aria-label="Account settings"
            >
              {account.photoURL ? (
                <img src={account.photoURL} alt="Profile" className="h-full w-full object-cover" />
              ) : (
                initials
              )}
            </Link>
          )}
          {account ? (
            <>
              <Link
                href="/settings"
                className="hidden items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-card)] px-2 py-1 no-underline shadow-sm sm:inline-flex"
                aria-label="Open account settings"
              >
                <span className="inline-flex h-7 w-7 items-center justify-center overflow-hidden rounded-full bg-[var(--color-primary)]/15 text-xs font-semibold text-[var(--color-primary)]">
                  {account.photoURL ? (
                    <img src={account.photoURL} alt="Profile" className="h-full w-full object-cover" />
                  ) : (
                    initials
                  )}
                </span>
                <span className="max-w-32 truncate pr-1 text-xs font-medium text-[var(--color-muted-foreground)]">
                  {account.displayName ?? account.email ?? "Account"}
                </span>
              </Link>
              <button
                type="button"
                onClick={() => void signOut()}
                className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-[var(--color-muted)]/40"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              href="/auth/login"
              className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-[var(--color-muted)]/40"
            >
              Sign in
            </Link>
          )}
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
