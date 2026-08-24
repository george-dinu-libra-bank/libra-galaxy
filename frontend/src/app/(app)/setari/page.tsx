import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SetariClient } from "@/components/setari/setari-client";
import { checkAdmin } from "@/lib/admin";
import { inregistreazaDispozitiv, obtineDispozitiveUtilizator } from "@/lib/data/dispozitive";
import { createClient } from "@/lib/supabase/server";
import { TEMA_COOKIE, temaDinCookie } from "@/lib/tema";

export const metadata: Metadata = {
  title: "Setări · Galaxy Bank",
};

export default async function SetariPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profil } = await supabase
    .from("profiles")
    .select("nume, cnp, telefon, email, avatar_url, verification_status")
    .eq("id", user.id)
    .single();

  if (!profil) {
    return (
      <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
        <p className="text-[15px] text-ink-soft">Profilul nu a fost găsit.</p>
      </div>
    );
  }

  // Citit separat, nu in select-ul de mai sus: coloana vine din migratia 0019,
  // care se aplica manual. Pusa acolo, lipsa ei ar rupe `.single()` si toata
  // pagina de setari ar afisa "Profilul nu a fost gasit".
  const { data: randBiometrie } = await supabase
    .from("profiles")
    .select("biometrie_activata")
    .eq("id", user.id)
    .maybeSingle();

  const biometrieActivata = randBiometrie?.biometrie_activata ?? true;

  const tema = temaDinCookie((await cookies()).get(TEMA_COOKIE)?.value);

  // Zona de administrare nu se anunta celor care n-au ce cauta in ea.
  const esteAdmin = (await checkAdmin()) !== null;

  // Upsert INAINTE de citire: asa dispozitivul celui care tocmai deschide
  // pagina e mereu in lista si mereu marcat corect ca "acest dispozitiv",
  // inclusiv pentru cine era deja logat cand a aparut functia.
  await inregistreazaDispozitiv();
  const dispozitive = await obtineDispozitiveUtilizator();

  return (
    <SetariClient
      profil={profil}
      tema={tema}
      esteAdmin={esteAdmin}
      biometrieActivata={biometrieActivata}
      dispozitive={dispozitive}
    />
  );
}
