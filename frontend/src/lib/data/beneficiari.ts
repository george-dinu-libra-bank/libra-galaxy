import { createClient } from "@/lib/supabase/server";

export type Beneficiar = {
  id: string;
  nume: string;
  iban: string;
  banca: string;
  favorit: boolean;
  /**
   * Proprietarul contului Galaxy Bank cu acest IBAN, daca exista — completat
   * automat la adaugare, prin potrivire de IBAN (0045_beneficiari.sql). Null
   * pentru un beneficiar extern (alta banca): poate fi platit, dar nu poate fi
   * invitat intr-un grup.
   */
  idUserLegat: string | null;
};

/** Beneficiarii salvati de utilizatorul curent, favoritii primii. */
export async function obtineBeneficiariiMei(): Promise<Beneficiar[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("beneficiari")
    .select("id, nume, iban, banca, favorit, id_user_legat")
    .order("favorit", { ascending: false })
    .order("creat_la", { ascending: false });

  if (error) throw error;

  return (data ?? []).map((beneficiar) => ({
    id: beneficiar.id as string,
    nume: beneficiar.nume as string,
    iban: beneficiar.iban as string,
    banca: beneficiar.banca as string,
    favorit: beneficiar.favorit as boolean,
    idUserLegat: (beneficiar.id_user_legat as string | null) ?? null,
  }));
}
