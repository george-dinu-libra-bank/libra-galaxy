import type { Metadata } from "next";
import { ListaCarduri } from "@/components/carduri/lista-carduri";
import { obtineCarduriUtilizator } from "@/lib/data/carduri";
import { obtineConturiUtilizator } from "@/lib/data/conturi";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Carduri · Galaxy Bank",
};

export default async function CarduriPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Conturile se aduc si ele: fara ele nu se poate emite un card nou, fiindca
  // fiecare card apartine unui cont anume.
  //
  // Numele vine din profil, nu din card: `carduri` nu are asa ceva, si nici n-ar
  // trebui — pe un card tiparit numele posesorului e o copie a celui din actul
  // de identitate, nu un camp de sine statator. Daca lipseste, randul lui de pe
  // card dispare cu totul, fara sa lase un gol.
  const [carduri, conturi, profil] = await Promise.all([
    obtineCarduriUtilizator(),
    obtineConturiUtilizator(),
    user
      ? supabase.from("profiles").select("nume").eq("id", user.id).maybeSingle()
      : Promise.resolve({ data: null }),
  ]);

  const nume = (profil?.data?.nume as string | null | undefined) ?? null;

  return <ListaCarduri carduri={carduri} conturi={conturi} posesor={nume} />;
}
