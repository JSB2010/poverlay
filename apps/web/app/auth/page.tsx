import { redirect } from "next/navigation";

type SearchParams = Record<string, string | string[] | undefined>;

function readParam(value: string | string[] | undefined): string | null {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value) && typeof value[0] === "string") {
    return value[0];
  }
  return null;
}

export default function AuthIndexPage({ searchParams }: { searchParams?: SearchParams }) {
  const mode = readParam(searchParams?.mode);
  const next = readParam(searchParams?.next);
  const suffix = next && next.startsWith("/") ? `?next=${encodeURIComponent(next)}` : "";

  if (mode === "sign-up") {
    redirect(`/auth/register${suffix}`);
  }
  if (mode === "reset") {
    redirect(`/auth/reset${suffix}`);
  }
  redirect(`/auth/login${suffix}`);
}
