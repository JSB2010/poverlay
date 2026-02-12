import type { Metadata } from "next";
import { RequireAuth } from "@/components/require-auth";

export const metadata: Metadata = {
  title: "Media",
  description: "Manage rendered clips and download telemetry overlay outputs.",
};

export default function MediaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RequireAuth>{children}</RequireAuth>;
}
