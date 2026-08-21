import type { Metadata } from "next";
import { UserPlus } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = {
  title: "Deschide cont · Galaxy Bank",
  description: "Deschide un cont curent Galaxy Bank, cu IBAN romanesc, in cateva minute.",
};

export default function RegisterPage() {
  return (
    <AuthShell
      eyebrow="Cont nou"
      titlu="Deschide-ti contul"
      subtitlu="Ai nevoie de 2 minute si de actul de identitate la indemana."
      icoana={UserPlus}
      inapoi="/login"
    >
      <RegisterForm />
    </AuthShell>
  );
}
