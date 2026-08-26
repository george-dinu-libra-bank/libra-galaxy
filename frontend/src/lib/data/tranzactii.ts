import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/** Celalalt participant: destinatarul la „trimisa", expeditorul la „primita". */
export type Contraparte = {
  id: string;
  nume: string;
  avatarUrl: string | null;
};

/** Grupul implicat: „in" la o depunere, „din" la o plata din soldul comun. */
export type GrupTranzactie = {
  id: number;
  nume: string;
  directie: "in" | "din";
};

export type TranzactieAfisata = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creatLa: string;
  tip: "trimisa" | "primita";
  contraparte: Contraparte | null;
  /**
   * Numele de afisat pentru celalalt participant, calculat o singura data aici.
   *
   * Cand contrapartea lipseste sunt doua cazuri diferite, care arata la fel in
   * date: contul a fost sters, sau tranzactia n-a avut niciodata o persoana
   * dincolo (miscari de sistem, depuneri). Le distinge marcajul pus de
   * migratia 0034 la stergerea profilului — fara el, cele 504 miscari de
   * sistem existente ar fi aparut toate ca "Cont sters".
   */
  numeContraparte: string;
  /** Mutare intre doua conturi ale aceleiasi persoane — nu a plecat niciun ban. */
  intreConturiProprii: boolean;
  /** Setat doar la miscarile care ating soldul unui grup. */
  grup: GrupTranzactie | null;
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

  const COLOANE_DE_BAZA =
    "id, suma, valuta, descriere, creat_la, id_user_send, id_user_recieve, " +
    "id_group_send, id_group_recieve";

  function interogheaza(coloane: string) {
    const cerere = supabase
      .from("tranzactii")
      .select(coloane)
      .or(`id_user_send.eq.${user!.id},id_user_recieve.eq.${user!.id}`)
      .order("creat_la", { ascending: false });

    return limita ? cerere.limit(limita) : cerere;
  }

  let { data, error } = await interogheaza(`${COLOANE_DE_BAZA}, send_sters, recieve_sters`);

  // Marcajele vin din migratia 0034, aplicata manual pe Supabase cloud. Pana
  // atunci lipsesc, si nu e un motiv sa pice dashboardul si istoricul: reluam
  // fara ele, iar contrapartile lipsa raman "Cont Galaxy Bank", exact ca inainte.
  if (error && (error.code === "42703" || error.code === "PGRST204")) {
    ({ data, error } = await interogheaza(COLOANE_DE_BAZA));
  }

  if (error) throw error;

  // `select()` cu un sir construit dinamic nu-i mai da lui supabase-js forma
  // randului, deci tipul se pune aici.
  const randuri = (data ?? []) as unknown as Array<Record<string, unknown>>;

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

  // Numele grupurilor care apar in propriile miscari. Ca si la profiluri, RLS
  // nu le-ar da (ai putea sa fi iesit intre timp din grup), deci se citesc cu
  // service_role — strict pentru id-urile din tranzactiile utilizatorului.
  const idGrupuri = [
    ...new Set(
      randuri
        .flatMap((t) => [t.id_group_send, t.id_group_recieve])
        .filter((id): id is number => typeof id === "number"),
    ),
  ];

  const numeGrupuri = new Map<number, string>();

  if (idGrupuri.length) {
    const supabaseAdmin = createAdminClient();

    const { data: grupuri, error: eroareGrupuri } = await supabaseAdmin
      .from("groups")
      .select("id, nume")
      .in("id", idGrupuri);

    if (eroareGrupuri) throw eroareGrupuri;

    for (const grup of grupuri ?? []) {
      numeGrupuri.set(grup.id as number, grup.nume as string);
    }
  }

  return randuri.map((tranzactie) => {
    const trimisa = tranzactie.id_user_send === user.id;
    const idContraparte = trimisa ? tranzactie.id_user_recieve : tranzactie.id_user_send;

    const idGrupSend = tranzactie.id_group_send as number | null;
    const idGrupRecieve = tranzactie.id_group_recieve as number | null;
    const idGrup = idGrupSend ?? idGrupRecieve;

    const grup: GrupTranzactie | null = idGrup
      ? {
          id: idGrup,
          nume: numeGrupuri.get(idGrup) ?? "Grup",
          directie: idGrupSend ? "din" : "in",
        }
      : null;

    // La o depunere nu exista beneficiar-persoana: contrapartea e grupul.
    const contraparte =
      grup?.directie === "in"
        ? { id: `grup-${grup.id}`, nume: grup.nume, avatarUrl: null }
        : (contraparti.get(idContraparte as string) ?? null);

    // Marcajul e pe partea CEALALTA decat cea a utilizatorului curent.
    const contrapartaStearsa = trimisa
      ? Boolean(tranzactie.recieve_sters)
      : Boolean(tranzactie.send_sters);

    return {
      id: tranzactie.id as string,
      suma: Number(tranzactie.suma),
      valuta: tranzactie.valuta as string,
      descriere: tranzactie.descriere as string | null,
      creatLa: tranzactie.creat_la as string,
      tip: trimisa ? ("trimisa" as const) : ("primita" as const),
      contraparte,
      numeContraparte:
        contraparte?.nume ?? (contrapartaStearsa ? "Cont șters" : "Cont Galaxy Bank"),
      // O plata din grup catre propriul cont are acelasi om la ambele capete,
      // dar nu e o mutare intre conturile tale: banii au venit din punga comuna.
      intreConturiProprii:
        !grup && tranzactie.id_user_send === tranzactie.id_user_recieve,
      grup,
    };
  });
}
