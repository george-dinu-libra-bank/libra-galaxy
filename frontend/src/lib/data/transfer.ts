import { obtineConturiUtilizator } from "@/lib/data/conturi";
import { obtineGrupurileMele } from "@/lib/data/grupuri";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/**
 * Datele ecranului de transfer. Dupa 0007_conturi_bancare.sql, si sursa si
 * destinatia sunt conturi bancare: utilizatorul alege din care dintre conturile
 * lui plateste, iar IBAN-ul introdus identifica un cont al beneficiarului.
 *
 * De la 0009_core_banking_groups.sql sursa poate fi si soldul unui grup din
 * care faci parte — destinatia ramane mereu un cont, dupa IBAN.
 */

export const BANCA_INTERNA = "Libra Bank";
export const VALUTA_IMPLICITA = "RON";

export type ContSursa = {
  /** Uuid-ul contului, sau id-ul grupului ca text cand `tip` e „grup". */
  id: string;
  nume: string;
  /** IBAN-ul mascat la conturi, numarul de membri la grupuri. */
  numarMascat: string;
  sold: number;
  valuta: string;
  blocat: boolean;
  tip: "cont" | "grup";
};

export type BeneficiarTransfer = {
  /** Id-ul contului beneficiar, nu al persoanei. */
  id: string;
  nume: string;
  iban: string;
  banca: string;
};

/**
 * Sursele din care utilizatorul curent poate trimite bani: intai conturile
 * lui, apoi soldurile grupurilor din care face parte.
 *
 * Grupurile vin la urma pentru ca plata din punga comuna e cazul mai rar —
 * si pentru ca prima sursa din lista e cea preselectata in formular.
 */
export async function obtineConturiTransfer(): Promise<ContSursa[]> {
  const [conturi, grupuri] = await Promise.all([
    obtineConturiUtilizator(),
    obtineGrupurileMele(),
  ]);

  return [
    ...conturi.map((cont) => ({
      id: cont.id,
      nume: cont.nume,
      numarMascat: cont.ibanMascat,
      sold: cont.sold,
      valuta: VALUTA_IMPLICITA,
      blocat: false,
      tip: "cont" as const,
    })),
    ...grupuri.map((grup) => ({
      id: String(grup.id),
      nume: grup.nume,
      numarMascat: grup.membri === 1 ? "1 membru" : `${grup.membri} membri`,
      sold: grup.sold,
      valuta: VALUTA_IMPLICITA,
      blocat: false,
      tip: "grup" as const,
    })),
  ];
}

/**
 * Beneficiarii recenti — conturile catre care utilizatorul a mai trimis bani
 * sau de la care a primit, cele mai recente primele.
 *
 * Conturile si profilurile altor oameni nu se pot citi cu cheia anon (RLS), asa
 * ca lista se compune cu service_role, dar strict pentru id-urile de cont care
 * apar deja in propriile tranzactii.
 */
export async function obtineBeneficiariRecenti(): Promise<BeneficiarTransfer[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("tranzactii")
    .select("id_user_send, id_cont_send, id_cont_recieve, creat_la")
    .or(`id_user_send.eq.${user.id},id_user_recieve.eq.${user.id}`)
    .order("creat_la", { ascending: false })
    .limit(100);

  if (error) throw error;

  // Conturile proprii nu sunt beneficiari in lista de „recenti".
  const conturiProprii = new Set((await obtineConturiUtilizator()).map((cont) => cont.id));

  // Ordinea de aici da ordinea din lista: contul cel mai recent primul.
  const idUri: string[] = [];

  for (const tranzactie of data ?? []) {
    const contrapartida =
      tranzactie.id_user_send === user.id
        ? (tranzactie.id_cont_recieve as string | null)
        : (tranzactie.id_cont_send as string | null);

    if (contrapartida && !conturiProprii.has(contrapartida) && !idUri.includes(contrapartida)) {
      idUri.push(contrapartida);
    }
  }

  if (idUri.length === 0) return [];

  const supabaseAdmin = createAdminClient();

  const { data: conturi, error: eroareConturi } = await supabaseAdmin
    .from("conturi_bancare")
    .select("id, iban, id_user, profiles ( nume )")
    .in("id", idUri);

  if (eroareConturi) throw eroareConturi;

  const dupaId = new Map<string, BeneficiarTransfer>(
    (conturi ?? []).map((cont) => {
      // PostgREST intoarce relatia ca obiect sau ca lista, dupa cum o deduce.
      const relatie = cont.profiles as { nume: string } | { nume: string }[] | null;
      const proprietar = Array.isArray(relatie) ? relatie[0] : relatie;

      return [
        cont.id as string,
        {
          id: cont.id as string,
          nume: proprietar?.nume ?? "Cont Libra",
          iban: cont.iban as string,
          banca: BANCA_INTERNA,
        },
      ];
    }),
  );

  return idUri.map((id) => dupaId.get(id)).filter((b): b is BeneficiarTransfer => Boolean(b));
}
