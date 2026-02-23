import { Suspense } from "react";
import { AuthScreen, AuthScreenFallback } from "@/app/auth/_components/auth-screen";

export default function ResetPage() {
  return (
    <Suspense fallback={<AuthScreenFallback />}>
      <AuthScreen mode="reset" />
    </Suspense>
  );
}
