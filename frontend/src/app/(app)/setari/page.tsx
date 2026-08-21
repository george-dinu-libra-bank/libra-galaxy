import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SetariClient } from "@/components/setari/setari-client";
import { checkAdmin } from "@/lib/admin";
import { createClient } from "@/lib/supabase/server";
import { TEMA_COOKIE, temaDinCookie } from "@/lib/tema";

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

  const tema = temaDinCookie((await cookies()).get(TEMA_COOKIE)?.value);
  // Zona de administrare nu se anunta celor care n-au ce cauta in ea.
  const esteAdmin = (await checkAdmin()) !== null;

  return <SetariClient profil={profil} tema={tema} esteAdmin={esteAdmin} />;
}
