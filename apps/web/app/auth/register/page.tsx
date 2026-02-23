import { Suspense } from "react";
import { AuthScreen, AuthScreenFallback } from "@/app/auth/_components/auth-screen";

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthScreenFallback />}>
      <AuthScreen mode="register" />
    </Suspense>
  );
}
