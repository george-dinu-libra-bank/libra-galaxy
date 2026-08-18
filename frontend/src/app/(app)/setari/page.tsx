import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SetariClient } from "@/components/setari/setari-client";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Setări · Libra",
};

export default async function SetariPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profil } = await supabase
    .from("profiles")
    .select("nume, cnp, telefon, email")
    .eq("id", user.id)
    .single();

  if (!profil) {
    return (
      <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
        <p className="text-[15px] text-ink-soft">Profilul nu a fost găsit.</p>
      </div>
    );
  }

  return <SetariClient profil={profil} />;
}
