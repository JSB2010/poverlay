import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Account",
  description: "Sign in to POVerlay or create an account to manage renders and downloads.",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
