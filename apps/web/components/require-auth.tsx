"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isEnabled, isLoading, account } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isEnabled || isLoading || account) {
      return;
    }

    const nextPath = pathname || "/studio";
    router.replace(`/auth/login?next=${encodeURIComponent(nextPath)}`);
  }, [account, isEnabled, isLoading, pathname, router]);

  if (!isEnabled) {
    return <>{children}</>;
  }

  if (isLoading || !account) {
    return (
      <main className="mx-auto flex min-h-[45vh] w-full max-w-2xl items-center justify-center px-4 text-center">
        <div>
          <p className="text-sm font-medium text-[var(--color-primary)]">Checking session</p>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">Redirecting to sign-in if needed...</p>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
