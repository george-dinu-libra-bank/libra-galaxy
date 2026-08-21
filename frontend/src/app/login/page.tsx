import type { Metadata } from "next";
import { Lock } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = {
  title: "Autentificare · Galaxy Bank",
  description: "Intra in contul tau Galaxy Bank.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ redirectTo?: string }>;
}) {
  const { redirectTo } = await searchParams;

  // Acceptam doar rute interne, ca sa nu putem fi folositi ca open redirect.
  const destinatie =
    redirectTo && redirectTo.startsWith("/") && !redirectTo.startsWith("//")
      ? redirectTo
      : undefined;

  return (
    <AuthShell
      eyebrow="Autentificare"
      titlu="Bine ai revenit"
      subtitlu="Intra in cont ca sa iti vezi soldul si tranzactiile."
      icoana={Lock}
      inapoi="/"
    >
      <LoginForm redirectTo={destinatie} />
    </AuthShell>
  );
}
