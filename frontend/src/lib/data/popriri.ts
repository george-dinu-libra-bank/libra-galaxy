import { createClient } from "@/lib/supabase/server";

/**
 * Poprirea, asa cum o vede clientul.
 *
 * Se citeste cu clientul UTILIZATORULUI, nu cu service-role: politica de select
 * din 0047 ii da doar randurile lui. Nu e o comoditate — e diferenta dintre „isi
 * vede poprirea" si „poate intreba cat are de platit oricine altcineva". Din
 * acelasi motiv `poprire_rest_de_plata` e revocata pentru `authenticated`: e
 * `security definer` si primeste id-ul ca parametru.
 *
 * Poprirea sta pe OM, nu pe cont (vezi antetul migratiei), deci si aici se
 * intoarce o singura valoare pentru tot ecranul, nu una per cont.
 */
export type PoprireClient = {
  /** Cat mai e de virat, insumat peste toate popririle active, in RON. */
  restDePlata: number;
  /** Cine cere banii. La mai multe popriri, primul si un „si încă N". */
  creditor: string;
  /** Cate popriri active are, ca textul sa nu minta cand sunt mai multe. */
  numar: number;
};

export async function obtinePoprireaActiva(): Promise<PoprireClient | null> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const { data, error } = await supabase
    .from("popriri")
    .select("creditor, suma_totala, suma_incasata")
    .eq("id_utilizator", user.id)
    .eq("status", "activa")
    .order("creat_la", { ascending: true });

  // La eroare nu ascundem ecranul: bariera adevarata e in baza de date, iar un
  // dashboard cazut ar fi mai rau decat unul fara eticheta. Dar se logheaza —
  // lectia din `lib/data/credite.ts`, unde un `?? []` tacut a facut o zona
  // intreaga sa para goala in loc de stricata.
  if (error) {
    console.error("ERROR obtinePoprireaActiva:", error);
    return null;
  }

  if (!data || data.length === 0) return null;

  const restDePlata = data.reduce(
    (total, p) => total + (Number(p.suma_totala) - Number(p.suma_incasata)),
    0,
  );

  if (restDePlata <= 0) return null;

  return {
    restDePlata,
    creditor: data[0].creditor as string,
    numar: data.length,
  };
}
