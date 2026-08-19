import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/** Celalalt participant: destinatarul la „trimisa", expeditorul la „primita". */
export type Contraparte = {
  id: string;
  nume: string;
  avatarUrl: string | null;
};

export type TranzactieAfisata = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creatLa: string;
  tip: "trimisa" | "primita";
  contraparte: Contraparte | null;
  /** Mutare intre doua conturi ale aceleiasi persoane — nu a plecat niciun ban. */
  intreConturiProprii: boolean;
};

/**
 * Tranzactiile in care utilizatorul curent e expeditor sau destinatar, cele mai
 * noi primele. `limita` taie lista pentru rezumatul de pe dashboard.
 */
export async function obtineTranzactiiUtilizator(
  limita?: number,
): Promise<TranzactieAfisata[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  let cerere = supabase
    .from("tranzactii")
    .select("id, suma, valuta, descriere, creat_la, id_user_send, id_user_recieve")
    .or(`id_user_send.eq.${user.id},id_user_recieve.eq.${user.id}`)
    .order("creat_la", { ascending: false });

  if (limita) cerere = cerere.limit(limita);

  const { data, error } = await cerere;

  if (error) throw error;

  const randuri = data ?? [];

  const idContraparti = [
    ...new Set(
      randuri
        .map((t) => (t.id_user_send === user.id ? t.id_user_recieve : t.id_user_send))
        .filter(Boolean) as string[],
    ),
  ];

  // RLS pe profiles lasa fiecare cont sa vada doar propriul rand (0001_profiles.sql),
  // deci numele si poza celuilalt se citesc cu service_role — strict pentru
  // id-urile care apar deja in tranzactiile utilizatorului, nimic in plus.
  const contraparti = new Map<string, Contraparte>();

  if (idContraparti.length) {
    const supabaseAdmin = createAdminClient();

    const { data: profile, error: eroareProfile } = await supabaseAdmin
      .from("profiles")
      .select("id, nume, avatar_url")
      .in("id", idContraparti);

    if (eroareProfile) throw eroareProfile;

    for (const profil of profile ?? []) {
      contraparti.set(profil.id as string, {
        id: profil.id as string,
        nume: profil.nume as string,
        avatarUrl: (profil.avatar_url as string | null) ?? null,
      });
    }
  }

  return randuri.map((tranzactie) => {
    const trimisa = tranzactie.id_user_send === user.id;
    const idContraparte = trimisa ? tranzactie.id_user_recieve : tranzactie.id_user_send;

    return {
      id: tranzactie.id as string,
      suma: Number(tranzactie.suma),
      valuta: tranzactie.valuta as string,
      descriere: tranzactie.descriere as string | null,
      creatLa: tranzactie.creat_la as string,
      tip: trimisa ? ("trimisa" as const) : ("primita" as const),
      contraparte: contraparti.get(idContraparte as string) ?? null,
      intreConturiProprii: tranzactie.id_user_send === tranzactie.id_user_recieve,
    };
  });
}
