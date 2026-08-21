import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { VALUTE, type Curs, type Valuta } from "@/lib/valute";

/**
 * Aducerea cursurilor valutare si scrierea lor in public.curs_valutar
 * (0013_schimb_valutar.sql). Modul de server: importa „next/headers" prin
 * lib/supabase/server, deci NU se importa din componente client — acelea iau
 * constantele si converteste() din lib/valute.
 *
 * Cursul nu vine niciodata de la client: functiile din baza de date citesc
 * exclusiv tabela, iar tabela o scrie doar codul de aici, cu service_role.
 * Altfel oricine ar putea trimite „1 EUR = 100 RON" si si-ar tipari bani.
 */

/** Cursurile de referinta BNR, actualizate in zilele lucratoare in jur de ora 13. */
const URL_BNR = "https://www.bnr.ro/nbrfxrates.xml";

/**
 * Rezerva, cand BNR nu raspunde: cursurile de referinta BCE, publicate zilnic.
 * Nu sunt identice cu cele BNR (difera in a treia zecimala), de aceea salvam si
 * sursa si o aratam in interfata — nu scriem „curs BNR" peste altceva.
 */
const URL_REZERVA = "https://api.frankfurter.dev/v1/latest";

/** Sub o ora nu mai deranjam sursa: cursul zilei nu se schimba intre timp. */
const PROSPETIME_MS = 60 * 60 * 1000;

type Cursuri = { cursuri: Map<string, number>; data: string | null; sursa: string };

const STRAINE = VALUTE.filter((valuta) => valuta !== "RON");

/**
 * Citeste XML-ul BNR fara parser: formatul e plat —
 * `<Rate currency="EUR">4.9755</Rate>`, uneori cu `multiplier="100"` la valutele
 * marunte. Un parser XML intreg ar fi o dependinta pentru cinci randuri.
 */
function extrageDinBnr(xml: string): Cursuri {
  const cursuri = new Map<string, number>();
  const potrivireData = xml.match(/<Cube\s+date="(\d{4}-\d{2}-\d{2})"/);

  const randuri = xml.matchAll(
    /<Rate\s+currency="([A-Z]{3})"(?:\s+multiplier="(\d+)")?\s*>([\d.]+)<\/Rate>/g,
  );

  for (const [, valuta, multiplicator, valoare] of randuri) {
    const numar = Number(valoare);
    const impartitor = multiplicator ? Number(multiplicator) : 1;

    if (!Number.isFinite(numar) || numar <= 0 || impartitor <= 0) continue;

    // Normalizam la „RON pentru o unitate", ca tabela sa nu mai poarte
    // multiplicatorul mai departe in fiecare conversie.
    cursuri.set(valuta, numar / impartitor);
  }

  return { cursuri, data: potrivireData?.[1] ?? null, sursa: "BNR" };
}

async function aduDeLaBnr(): Promise<Cursuri | null> {
  try {
    const raspuns = await fetch(URL_BNR, {
      // Prospetimea o decidem noi, dupa `actualizat_la` din tabela; cache-ul
      // Next ar adauga inca un strat cu alta parere despre ea.
      cache: "no-store",
      headers: { Accept: "application/xml" },
      signal: AbortSignal.timeout(8000),
    });

    if (!raspuns.ok) throw new Error(`BNR a raspuns ${raspuns.status}`);

    const text = await raspuns.text();

    // WAF-ul BNR raspunde uneori cu 200 si pagina de start (sau cu „Request
    // Rejected"), in loc de XML. Fara verificarea asta am fi crezut ca a mers si
    // am fi scris zero cursuri.
    if (!text.includes("<Rate")) {
      throw new Error("BNR a raspuns cu HTML, nu cu XML (probabil filtru anti-bot)");
    }

    const rezultat = extrageDinBnr(text);

    if (STRAINE.every((valuta) => rezultat.cursuri.has(valuta))) return rezultat;

    //throw new Error("BNR nu a returnat toate valutele cerute");
  } catch (eroare) {
    // warn, nu error: BNR-ul care ne refuza e o situatie asteptata, cu rezerva
    // pregatita imediat mai jos. Cu console.error, overlay-ul de dezvoltare din
    // Next se ridica peste toata pagina si arata ca un ecran cazut, desi
    // fallback-ul functioneaza si dashboard-ul s-ar randa normal.
    console.warn("curs valutar: BNR indisponibil, incerc rezerva —", mesaj(eroare));
    return null;
  }
}

async function aduDeLaRezerva(): Promise<Cursuri | null> {
  try {
    const adresa = `${URL_REZERVA}?base=RON&symbols=${STRAINE.join(",")}`;

    const raspuns = await fetch(adresa, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(8000),
    });

    if (!raspuns.ok) throw new Error(`Sursa de rezerva a raspuns ${raspuns.status}`);

    const corp = (await raspuns.json()) as {
      date?: string;
      rates?: Record<string, number>;
    };

    const cursuri = new Map<string, number>();

    for (const valuta of STRAINE) {
      const rata = corp.rates?.[valuta];

      // Sursa da „cate unitati face un RON"; noi tinem inversul.
      if (typeof rata === "number" && rata > 0) cursuri.set(valuta, 1 / rata);
    }

    if (cursuri.size === 0) throw new Error("Sursa de rezerva nu a returnat cursuri");

    return { cursuri, data: corp.date ?? null, sursa: "BCE (Frankfurter)" };
  } catch (eroare) {
    // Nici asta nu e fatal: ramanem pe ultimele cursuri din tabela.
    console.warn("curs valutar: nici sursa de rezerva nu raspunde —", mesaj(eroare));
    return null;
  }
}

/** Doar mesajul, nu obiectul Error: altfel Next ridica overlay-ul de eroare. */
function mesaj(eroare: unknown): string {
  return eroare instanceof Error ? eroare.message : String(eroare);
}

/**
 * Aduce cursurile si le scrie in tabela, daca cele din tabela au imbatranit.
 * Esecul nu arunca: daca nu raspunde nici BNR si nici rezerva, ramanem pe
 * ultimele cursuri stiute — mai bine un curs de ieri decat un ecran rupt.
 */
async function improspateazaCursuri(celMaiVechi: string | null) {
  if (celMaiVechi && Date.now() - new Date(celMaiVechi).getTime() < PROSPETIME_MS) {
    return;
  }

  const rezultat = (await aduDeLaBnr()) ?? (await aduDeLaRezerva());

  if (!rezultat) return;

  const randuri = STRAINE.filter((valuta) => rezultat.cursuri.has(valuta)).map((valuta) => ({
    valuta,
    curs: rezultat.cursuri.get(valuta)!,
    data_curs: rezultat.data ?? new Date().toISOString().slice(0, 10),
    sursa: rezultat.sursa,
    actualizat_la: new Date().toISOString(),
  }));

  if (randuri.length === 0) return;

  // Scrierea cere service_role: pe curs_valutar nu exista nicio politica de
  // INSERT/UPDATE, tocmai ca niciun client sa nu-si poata inventa cursul.
  const admin = createAdminClient();
  const { error } = await admin.from("curs_valutar").upsert(randuri, { onConflict: "valuta" });

  if (error) console.error("ERROR curs valutar (upsert):", error);
}

/**
 * Cursurile pentru valutele acceptate, cel de RON inclus (mereu 1).
 *
 * Intai citim ce avem, si abia daca e vechi mergem la BNR — asa ecranul se
 * randeaza cu ce stim si nu asteapta o cerere externa la fiecare afisare.
 */
export async function obtineCursuri(): Promise<Curs[]> {
  const supabase = await createClient();

  const citeste = async () =>
    supabase.from("curs_valutar").select("valuta, curs, data_curs, sursa, actualizat_la");

  let { data, error } = await citeste();

  // Nu aruncam: inainte de rularea lui 0013 tabela nici nu exista, iar un
  // dashboard cazut ar fi o pedeapsa disproportionata pentru o migratie
  // neaplicata. Fara cursuri, conturile in RON se aduna in continuare corect
  // (converteste() iese devreme cand valuta e aceeasi), iar schimbul valutar
  // spune singur ca nu are cursuri.
  if (error) {
    console.error("ERROR obtineCursuri (citire):", error);
    return [];
  }

  const celMaiVechi = (data ?? [])
    .map((rand) => rand.actualizat_la as string)
    .sort()
    .at(0);

  await improspateazaCursuri((data ?? []).length === 0 ? null : (celMaiVechi ?? null));

  // A doua citire doar daca prima chiar era invechita sau goala.
  if (!celMaiVechi || Date.now() - new Date(celMaiVechi).getTime() >= PROSPETIME_MS) {
    ({ data, error } = await citeste());

    if (error) {
      console.error("ERROR obtineCursuri (recitire):", error);
      return [];
    }
  }

  const cunoscute = new Set<string>(VALUTE);

  return (data ?? [])
    .filter((rand) => cunoscute.has(rand.valuta as string))
    .map((rand) => ({
      valuta: rand.valuta as Valuta,
      curs: Number(rand.curs),
      dataCurs: rand.data_curs as string,
      sursa: (rand.sursa as string) ?? "BNR",
    }))
    .sort((a, b) => VALUTE.indexOf(a.valuta) - VALUTE.indexOf(b.valuta));
}
