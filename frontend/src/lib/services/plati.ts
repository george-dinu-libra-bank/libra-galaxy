import { obtineProdus } from "@/lib/data/produse";
import type { StarePlata } from "@/lib/plati";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/**
 * Logica platilor de card confirmate din aplicatie. Rutele din
 * app/api/payments/* raman subtiri si doar traduc intre HTTP si functiile de
 * aici, ca in ARCHITECTURE.md (12).
 *
 * Regulile bancare stau in SQL (0014_payments.sql): aici se face autentificarea,
 * se stabileste suma din catalog si se traduc codurile de eroare.
 */

export type Plata = {
  id: string;
  status: StarePlata;
  suma: number;
  valuta: string;
  comerciant: string;
  descriere: string | null;
  cardUltimele4: string;
  motiv: string | null;
  expiraLa: string | null;
};

export type RezultatPlata =
  | { ok: true; plata: Plata }
  | { ok: false; eroare: string; http: number };

/** Numele sub care apare magazinul pe extrasul de cont. */
export const COMERCIANT = "Galaxy Shop";

/** Cat are utilizatorul la dispozitie sa confirme, in secunde. */
export const SECUNDE_CONFIRMARE = 120;

/** Codurile ridicate de functiile din 0014_payments.sql. */
const MESAJE: Record<string, string> = {
  NEAUTENTIFICAT: "Trebuie să fii autentificat în Libra.",
  SUMA_INVALIDA: "Suma comenzii este invalidă.",
  VALUTA_NESUPORTATA: "Valuta comenzii nu este acceptată.",
  DATE_CARD_GRESITE: "Datele cardului nu corespund niciunui card Libra al tău.",
  CARD_BLOCAT: "Cardul este blocat. Deblochează-l din secțiunea Carduri.",
  CARD_EXPIRAT: "Cardul a expirat.",
  FARA_CONT: "Nu ai niciun cont bancar din care să se poată plăti.",
  FONDURI_INSUFICIENTE: "Nu ai fonduri suficiente pentru această plată.",
  PLATA_INEXISTENTA: "Plata nu există sau nu îți aparține.",
};

/** Randul brut intors de RPC-urile de plati. */
type RandPlata = {
  id: string;
  status: string;
  suma: string | number;
  valuta: string;
  comerciant: string;
  descriere: string | null;
  card_ultimele4: string;
  motiv: string | null;
  expira_la: string | null;
};

function mapeaza(rand: RandPlata): Plata {
  return {
    id: rand.id,
    status: rand.status as StarePlata,
    suma: Number(rand.suma),
    valuta: rand.valuta,
    comerciant: rand.comerciant,
    descriere: rand.descriere,
    cardUltimele4: rand.card_ultimele4,
    motiv: rand.motiv,
    expiraLa: rand.expira_la,
  };
}

/** Traduce eroarea PostgREST in mesaj pentru utilizator plus cod HTTP. */
function laEroare(error: { message: string }, context: string): RezultatPlata {
  const mesaj = MESAJE[error.message];

  // Orice altceva (functia lipseste, deadlock, retea) — log si mesaj generic.
  if (!mesaj) console.error(`ERROR ${context}:`, error);

  return {
    ok: false,
    eroare: mesaj ?? "Nu am putut procesa plata. Încearcă din nou.",
    http: error.message === "PLATA_INEXISTENTA" ? 404 : mesaj ? 400 : 500,
  };
}

/** Id-ul utilizatorului din sesiune, sau null daca nu e autentificat. */
async function idUtilizatorCurent() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  return user?.id ?? null;
}

/**
 * Deschide o plata pentru un produs din magazin.
 *
 * Suma nu vine niciodata din formular: se citeste din catalog dupa slug, ca un
 * client sa nu-si poata alege pretul. Din datele cardului, CVV-ul serveste doar
 * la verificare — in `payments` ajung doar ultimele patru cifre.
 */
export async function creeazaPlata(input: {
  slug: string;
  numarCard: string;
  dataExpirare: string;
  cvv: string;
}): Promise<RezultatPlata> {
  const idUser = await idUtilizatorCurent();

  if (!idUser) return { ok: false, eroare: MESAJE.NEAUTENTIFICAT, http: 401 };

  const produs = obtineProdus(input.slug);

  if (!produs) return { ok: false, eroare: "Produsul nu există.", http: 404 };

  const numarCard = input.numarCard.replace(/\D/g, "");
  const dataExpirare = input.dataExpirare.trim();
  const cvv = input.cvv.trim();

  // Validari ieftine de formular; adevarul il spune tot baza de date.
  if (
    numarCard.length !== 16 ||
    !/^(0[1-9]|1[0-2])\/[0-9]{2}$/.test(dataExpirare) ||
    !/^\d{3}$/.test(cvv)
  ) {
    return { ok: false, eroare: MESAJE.DATE_CARD_GRESITE, http: 400 };
  }

  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin.rpc("creeaza_plata", {
    p_id_user: idUser,
    p_numar_card: numarCard,
    p_data_expirare: dataExpirare,
    p_ccv: cvv,
    p_suma: produs.pret,
    p_comerciant: COMERCIANT,
    p_descriere: `${COMERCIANT} · ${produs.nume}`,
    p_valuta: "RON",
    p_secunde: SECUNDE_CONFIRMARE,
  });

  if (error) return laEroare(error, "creeazaPlata");

  return { ok: true, plata: mapeaza(data as RandPlata) };
}

/** Confirma o plata proprie: revalidare, debitare si tranzactie, atomic in SQL. */
export async function aprobaPlata(idPlata: string): Promise<RezultatPlata> {
  return schimbaStarea("aproba_plata", idPlata, "aprobaPlata");
}

/** Respinge o plata proprie aflata in asteptare. */
export async function respingePlata(idPlata: string): Promise<RezultatPlata> {
  return schimbaStarea("respinge_plata", idPlata, "respingePlata");
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function schimbaStarea(
  rpc: "aproba_plata" | "respinge_plata",
  idPlata: string,
  context: string,
): Promise<RezultatPlata> {
  const idUser = await idUtilizatorCurent();

  if (!idUser) return { ok: false, eroare: MESAJE.NEAUTENTIFICAT, http: 401 };

  if (!UUID.test(idPlata ?? "")) return { ok: false, eroare: MESAJE.PLATA_INEXISTENTA, http: 404 };

  const supabaseAdmin = createAdminClient();

  const { data, error } = await supabaseAdmin.rpc(rpc, {
    p_id: idPlata,
    p_id_user: idUser,
  });

  if (error) return laEroare(error, context);

  return { ok: true, plata: mapeaza(data as RandPlata) };
}
