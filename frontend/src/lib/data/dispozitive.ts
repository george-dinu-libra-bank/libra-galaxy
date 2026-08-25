import "server-only";

import { headers } from "next/headers";
import { descrieDispozitiv } from "@/lib/dispozitive";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/**
 * Evidenta dispozitivelor de pe care s-a intrat in cont.
 *
 * Modul de server obisnuit, NU "use server": acolo fiecare export devine un
 * endpoint apelabil din browser, iar inregistrarea unui dispozitiv nu are ce
 * cauta in mainile clientului — oricine si-ar putea inventa randuri in propria
 * lista de securitate. Singura actiune chemata din client sta separat, in
 * lib/actions/dispozitive.ts.
 *
 * Tabela vine din migratia 0019, care se aplica manual pe Supabase cloud.
 * Pana atunci lipseste, si asta e o stare normala, nu o eroare — vezi
 * `tabelaLipseste`.
 */

const TABELA = "dispozitive_conectate";

/** Peste atat, randul nu mai spune nimic adevarat despre un dispozitiv "conectat". */
const ZILE_PANA_LA_UITARE = 30;

export type DispozitivAfisat = {
  id: string;
  eticheta: string;
  mobil: boolean;
  esteAcesta: boolean;
  /** ISO. Primul login de pe acest dispozitiv. */
  conectatLa: string;
};

type EroareSupabase = { code?: string } | null;

/**
 * 42P01 = relatia nu exista (Postgres); PGRST205 = PostgREST n-o are in cache-ul
 * de schema. Amandoua inseamna "migratia 0019 inca n-a fost rulata".
 */
function tabelaLipseste(eroare: EroareSupabase): boolean {
  return eroare?.code === "42P01" || eroare?.code === "PGRST205";
}

async function amprentaCurenta() {
  const antete = await headers();

  return {
    ...descrieDispozitiv({
      agentUtilizator: antete.get("user-agent"),
      platformaHint: antete.get("sec-ch-ua-platform"),
      mobilHint: antete.get("sec-ch-ua-mobile"),
    }),
    agentBrut: antete.get("user-agent"),
  };
}

/** session_id-ul sesiunii curente, sau null daca nu-l putem citi. */
async function idSesiuneCurenta(): Promise<string | null> {
  try {
    const supabase = await createClient();
    // getClaims() verifica tokenul prin JWKS — de aceea nu e nevoie de nicio
    // biblioteca de decodat JWT-uri.
    const { data } = await supabase.auth.getClaims();
    const id = data?.claims?.session_id;
    return typeof id === "string" ? id : null;
  } catch {
    return null;
  }
}

/**
 * Scrie sau actualizeaza randul dispozitivului de pe care vine cererea.
 *
 * Nu arunca niciodata si nu intoarce nimic: un login n-are voie sa esueze
 * pentru ca n-am reusit sa notam de pe ce browser a venit.
 *
 * Upsert-ul NU trimite `creat_la`, deci "primul login de pe acest dispozitiv"
 * supravietuieste re-logarilor — de-aia e coloana aceea utila.
 */
export async function inregistreazaDispozitiv(): Promise<void> {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    const dispozitiv = await amprentaCurenta();
    const supabaseAdmin = await createAdminClient();

    const { error } = await supabaseAdmin.from(TABELA).upsert(
      {
        id_user: user.id,
        amprenta: dispozitiv.amprenta,
        eticheta: dispozitiv.eticheta,
        agent_utilizator: dispozitiv.agentBrut,
        mobil: dispozitiv.mobil,
        id_sesiune: await idSesiuneCurenta(),
        ultima_activitate: new Date().toISOString(),
      },
      { onConflict: "id_user,amprenta" },
    );

    if (error && !tabelaLipseste(error)) {
      console.error("[dispozitive/inregistreaza]", error.message);
    }
  } catch (eroare) {
    console.error("[dispozitive/inregistreaza] cod=neasteptat", eroare);
  }
}

/**
 * Dispozitivele utilizatorului curent, cele mai recente primele.
 *
 * Curata la citire randurile mai vechi de 30 de zile, in loc de un job
 * periodic: proiectul n-are scheduler, iar singurul om caruia ii pasa ca lista
 * e curata e chiar cel care se uita la ea. O sesiune poate muri fara sa aflam
 * (cookie-uri sterse, token expirat), deci fara regula asta un dispozitiv ar
 * ramane afisat ca "conectat" la nesfarsit.
 *
 * Intoarce [] cand tabela lipseste: o pagina de securitate care da 500 fiindca
 * o migratie e in asteptare e mai rea decat una care arata o lista goala.
 */
export async function obtineDispozitiveUtilizator(): Promise<DispozitivAfisat[]> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return [];

  const supabaseAdmin = await createAdminClient();

  const pragUitare = new Date(Date.now() - ZILE_PANA_LA_UITARE * 24 * 60 * 60 * 1000);
  const { error: eroareCuratare } = await supabaseAdmin
    .from(TABELA)
    .delete()
    .eq("id_user", user.id)
    .lt("ultima_activitate", pragUitare.toISOString());

  if (eroareCuratare && tabelaLipseste(eroareCuratare)) return [];

  const { data, error } = await supabaseAdmin
    .from(TABELA)
    .select("id, eticheta, mobil, id_sesiune, creat_la")
    .eq("id_user", user.id)
    .order("ultima_activitate", { ascending: false });

  if (error) {
    if (tabelaLipseste(error)) return [];
    console.error("[dispozitive/obtine]", error.message);
    return [];
  }

  const sesiuneCurenta = await idSesiuneCurenta();

  return (data ?? []).map((rand) => ({
    id: rand.id as string,
    eticheta: rand.eticheta as string,
    mobil: Boolean(rand.mobil),
    esteAcesta: Boolean(sesiuneCurenta) && rand.id_sesiune === sesiuneCurenta,
    conectatLa: rand.creat_la as string,
  }));
}

/**
 * Sterge randul dispozitivului curent. Se apeleaza la delogare, INAINTE de
 * signOut: dupa, nu mai avem de unde sti pe ce sesiune eram.
 */
export async function stergeDispozitivulCurent(): Promise<void> {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    const dispozitiv = await amprentaCurenta();
    const supabaseAdmin = await createAdminClient();

    const { error } = await supabaseAdmin
      .from(TABELA)
      .delete()
      .eq("id_user", user.id)
      .eq("amprenta", dispozitiv.amprenta);

    if (error && !tabelaLipseste(error)) {
      console.error("[dispozitive/stergeCurent]", error.message);
    }
  } catch (eroare) {
    console.error("[dispozitive/stergeCurent] cod=neasteptat", eroare);
  }
}
