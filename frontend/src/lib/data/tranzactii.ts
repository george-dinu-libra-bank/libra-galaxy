import { createClient } from "@/lib/supabase/server";

export type TranzactieAfisata = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creatLa: string;
  tip: "trimisa" | "primita";
};

/** Tranzactiile in care utilizatorul curent e expeditor sau destinatar. */
export async function obtineTranzactiiUtilizator(): Promise<TranzactieAfisata[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("tranzactii")
    .select("id, suma, valuta, descriere, creat_la, id_user_send, id_user_recieve")
    .or(`id_user_send.eq.${user.id},id_user_recieve.eq.${user.id}`)
    .order("creat_la", { ascending: false });

  if (error) throw error;

  return (data ?? []).map((tranzactie) => ({
    id: tranzactie.id as string,
    suma: Number(tranzactie.suma),
    valuta: tranzactie.valuta as string,
    descriere: tranzactie.descriere as string | null,
    creatLa: tranzactie.creat_la as string,
    tip: tranzactie.id_user_send === user.id ? "trimisa" : "primita",
  }));
}
