import type { Metadata } from "next";
import { RequireAuth } from "@/components/require-auth";

export const metadata: Metadata = {
  title: "Admin Ops",
  description: "Queue, cleanup, and storage operations dashboard for POVerlay admins.",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RequireAuth>{children}</RequireAuth>;
}
