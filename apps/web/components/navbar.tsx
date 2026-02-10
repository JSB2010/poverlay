"use client";

import Link from "next/link";
import Image from "next/image";
import { ThemeToggle } from "./theme-toggle";

export function Navbar() {
  return (
    <nav className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3 text-foreground no-underline transition-opacity hover:opacity-80">
          <div className="relative h-10 w-10 overflow-hidden rounded-xl shadow-lg shadow-primary/20">
            <Image
              src="/logo.png"
              alt="POVerlay Logo"
              fill
              className="object-contain"
              priority
            />
          </div>
          <span className="text-2xl font-bold tracking-tight" style={{ fontFamily: "var(--font-display), system-ui, sans-serif" }}>
            POVerlay
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href="/studio"
            className="hidden rounded-lg px-3.5 py-1.5 text-sm font-medium text-muted-foreground no-underline transition-colors hover:text-foreground sm:inline-flex"
          >
            Studio
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}

