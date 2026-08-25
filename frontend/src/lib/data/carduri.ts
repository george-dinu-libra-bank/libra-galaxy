import { obtineConturiUtilizator } from "@/lib/data/conturi";
import { createClient } from "@/lib/supabase/server";

export type StilCard = "standard" | "silver" | "gold";
export type TipCard = "fizic" | "virtual";

export type CardAfisat = {
  id: string;
  stil: StilCard;
  tip: TipCard;
  numarMascat: string;
  dataExpirare: string;
  blocat: boolean;
  /**
   * Oprit de banca. Clientul nu poate ridica masura din aplicatie.
   * Adevarat si cand banca a blocat contul cardului, nu cardul in sine: efectul
   * pentru om e acelasi, si n-ar avea sens sa vada un card "activ" pe un cont
   * din care nu mai poate pleca niciun ban.
   */
  blocatDeBanca: boolean;

  /** Contul din care plateste cardul. Banii stau acolo, nu pe card. */
  idCont: string | null;
  numeCont: string | null;
  /** Soldul contului cardului, in valuta lui. */
  sold: number;
  valuta: string;

  /** Cat poate cheltui cardul intr-o zi, in valuta contului. null = fara limita. */
  limitaZilnica: number | null;
};

/**
 * Cardurile utilizatorului curent, fiecare cu contul lui.
 *
 * Pana la 0027 un card nu avea cont, iar interfata afisa pe FIECARE card
 * acelasi numar: totalul tuturor conturilor convertit in RON. Trei carduri
 * aratau aceeasi cifra, ca si cum ar fi fost trei portofele cu aceiasi bani.
 * Acum fiecare card arata soldul contului lui, in valuta lui.
 */
export async function obtineCarduriUtilizator(): Promise<CardAfisat[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const [{ data, error }, conturi] = await Promise.all([
    supabase
      .from("carduri")
      // Sirul ramane pe o linie: supabase-js isi deduce tipul din literal, iar o
      // concatenare il face `GenericStringError`.
      .select("id, numar_card, data_expirare, card_style, is_blocked, blocat_administrativ, creat_la, id_cont, tip, limita_zilnica")
      .eq("id_user", user.id)
      .order("creat_la", { ascending: true }),
    obtineConturiUtilizator(),
  ]);

  if (error) throw error;

  const dupaId = new Map(conturi.map((c) => [c.id, c]));

  return (data ?? []).map((card) => {
    const cont = card.id_cont ? dupaId.get(card.id_cont as string) : undefined;

    return {
      id: card.id as string,
      stil: card.card_style as StilCard,
      // `tip` nu exista pana la 0031; pana e rulata, orice card e fizic.
      tip: ((card.tip as TipCard) ?? "fizic") as TipCard,
      numarMascat: `•••• •••• •••• ${(card.numar_card as string).slice(-4)}`,
      dataExpirare: card.data_expirare as string,
      blocat: card.is_blocked as boolean,
      blocatDeBanca:
        ((card.blocat_administrativ as boolean) ?? false) || (cont?.blocatDeBanca ?? false),

      idCont: (card.id_cont as string) ?? null,
      numeCont: cont?.nume ?? null,
      sold: cont?.sold ?? 0,
      valuta: cont?.valuta ?? "RON",

      limitaZilnica: (card.limita_zilnica as number | null) ?? null,
    };
  });
}
