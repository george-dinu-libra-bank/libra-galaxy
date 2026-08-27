"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { contEsteBlocat, MESAJ_CONT_BLOCAT } from "@/lib/cont-blocat";

export type RezultatGrupNou = { id?: number; nume?: string; token?: string; eroare?: string };
export type RezultatIntrare = { id?: number; nume?: string; eroare?: string };
export type RezultatPreviziune = {
  id?: number;
  nume?: string;
  membri?: number;
  suntDeja?: boolean;
  eroare?: string;
};
export type RezultatMesaj = { eroare?: string };

/**
 * Mesajele pentru utilizator, dupa codul ridicat de functiile din
 * 0008_grupuri.sql: codul ajunge in `message`, textul lung in `details`.
 */
const MESAJE_GRUPURI: Record<string, string> = {
  NEAUTENTIFICAT: "Trebuie sa fii autentificat.",
  NUME_INVALID: "Numele grupului trebuie sa aiba intre 2 si 60 de caractere.",
  TOKEN_INVALID: "Codul grupului este invalid.",
  GRUP_INEXISTENT: "Nu exista niciun grup cu acest cod.",
  PREA_MULTE_GRUPURI: "Poti face parte din cel mult 30 de grupuri.",
  // Ridicate de core_banking_groups (0009_core_banking_groups.sql).
  NU_ESTI_MEMBRU: "Nu faci parte din acest grup.",
  SUMA_INVALIDA: "Introdu o suma valida.",
  VALUTA_NESUPORTATA: "Momentan se pot pune doar sume in RON.",
  CONT_SURSA_INEXISTENT: "Contul din care vrei sa pui bani nu exista.",
  CONT_SURSA_STRAIN: "Nu poti pune bani dintr-un cont care nu este al tau.",
  FONDURI_INSUFICIENTE: "Nu ai fonduri suficiente in cont.",
  // Trigger-ul din 0047 prinde si banii care pleaca spre punga comuna.
  POPRIRE_ACTIVA:
    "O parte din banii tăi sunt indisponibilizați printr-o poprire, iar suma cerută îi depășește pe cei disponibili.",
};

function mesajPentru(codul: string, implicit: string) {
  return MESAJE_GRUPURI[codul] ?? implicit;
}

/**
 * Curata ce a lipit utilizatorul in camp: accepta si tokenul simplu
 * („AB3D…"), si linkul intreg („https://…/grupuri?token=AB3D…").
 */
function normalizeazaToken(valoare: string) {
  const brut = valoare.trim();
  const dinLink = brut.match(/token=([^&\s]+)/i)?.[1] ?? brut;

  return dinLink.replace(/[\s-]/g, "").toUpperCase();
}

/** Creeaza un grup nou si il inscrie pe creator. Tokenul se genereaza in baza de date. */
export async function creeazaGrup(numeBrut: string): Promise<RezultatGrupNou> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const nume = numeBrut.trim();

  if (nume.length < 2 || nume.length > 60) {
    return { eroare: "Numele grupului trebuie să aibă între 2 și 60 de caractere." };
  }

  const { data, error } = await supabase.rpc("creeaza_grup", { p_nume: nume });

  if (error) {
    if (!MESAJE_GRUPURI[error.message]) console.error("ERROR creeazaGrup:", error);
    return { eroare: mesajPentru(error.message, "Nu am putut crea grupul. Încearcă din nou.") };
  }

  revalidatePath("/grupuri");

  return {
    id: data.id as number,
    nume: data.nume as string,
    token: data.token_acces as string,
  };
}

/** Ce se poate afla despre un grup avand doar codul: numele si cati membri are. */
export async function previzualizeazaGrup(tokenBrut: string): Promise<RezultatPreviziune> {
  const supabase = await createClient();

  const token = normalizeazaToken(tokenBrut);

  if (!token) return { eroare: "Introdu codul grupului." };

  const { data, error } = await supabase.rpc("grup_dupa_token", { p_token: token });

  if (error) {
    if (!MESAJE_GRUPURI[error.message]) console.error("ERROR previzualizeazaGrup:", error);
    return { eroare: mesajPentru(error.message, "Nu am putut căuta grupul. Încearcă din nou.") };
  }

  return {
    id: data.id as number,
    nume: data.nume as string,
    membri: data.membri as number,
    suntDeja: data.sunt_deja as boolean,
  };
}

/** Intra in grupul cu codul dat. Repetabil: daca esti deja inauntru, nu se schimba nimic. */
export async function intraInGrup(tokenBrut: string): Promise<RezultatIntrare> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const token = normalizeazaToken(tokenBrut);

  if (!token) return { eroare: "Introdu codul grupului." };

  const { data, error } = await supabase.rpc("intra_in_grup", { p_token: token });

  if (error) {
    if (!MESAJE_GRUPURI[error.message]) console.error("ERROR intraInGrup:", error);
    return { eroare: mesajPentru(error.message, "Nu am putut intra în grup. Încearcă din nou.") };
  }

  revalidatePath("/grupuri");

  return { id: data.id as number, nume: data.nume as string };
}

/**
 * Scrie un mesaj in grup. Merge pe clientul utilizatorului: politica de INSERT
 * verifica si ca autorul e el, si ca e membru al grupului.
 */
export async function trimiteMesaj(idGrup: number, continutBrut: string): Promise<RezultatMesaj> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const continut = continutBrut.trim();

  if (!continut) return { eroare: "Scrie un mesaj înainte de a-l trimite." };
  if (continut.length > 1000) return { eroare: "Mesajul poate avea cel mult 1000 de caractere." };

  // `type` explicit: politica de INSERT accepta din client doar 'text', ca sa
  // nu poata nimeni fabrica un anunt de incasare (0010_mesaje_incasare.sql).
  const { error } = await supabase
    .from("group_messages")
    .insert({ id_group: idGrup, id_user: user.id, continut, type: "text" });

  if (error) {
    console.error("ERROR trimiteMesaj:", error);
    return { eroare: "Nu am putut trimite mesajul. Încearcă din nou." };
  }

  revalidatePath(`/grupuri/${idGrup}`);

  return {};
}

/** Rotunjeste la banut, ca sa nu ramana resturi din aritmetica in virgula mobila. */
function laBanut(valoare: number) {
  return Number(valoare.toFixed(2));
}

/**
 * Pune bani din contul tau in soldul comun al grupului.
 *
 * Toata mutarea (verificari + debitare cont + creditare grup + istoric) se face
 * in public.core_banking_groups, intr-o singura tranzactie sub lock
 * (0009_core_banking_groups.sql). Aici raman doar validarile de formular.
 */
export async function depuneInGrup(input: {
  idGrup: number;
  idCont: string;
  suma: number;
  detalii?: string;
}): Promise<RezultatMesaj> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const suma = laBanut(input.suma);

  if (!Number.isFinite(suma) || suma <= 0) return { eroare: "Introdu o sumă validă." };

  // Depunerea scoate bani din contul propriu, deci un cont blocat nu o poate
  // face: altfel si-ar putea muta banii intr-un grup si i-ar scoate prin alt
  // membru. Vezi lib/cont-blocat.ts pentru ce acopera verificarea si ce nu.
  if (await contEsteBlocat(user.id)) return { eroare: MESAJ_CONT_BLOCAT };

  const { error } = await supabase.rpc("core_banking_groups", {
    p_id_group: input.idGrup,
    p_suma: suma,
    p_directie: "depunere",
    p_descriere: input.detalii?.trim() || null,
    p_id_cont: input.idCont,
  });

  if (error) {
    if (!MESAJE_GRUPURI[error.message]) console.error("ERROR depuneInGrup:", error);
    return { eroare: mesajPentru(error.message, "Nu am putut pune banii în grup. Încearcă din nou.") };
  }

  revalidatePath("/grupuri");
  revalidatePath(`/grupuri/${input.idGrup}`);
  revalidatePath("/dashboard");
  revalidatePath("/istoric");
  revalidatePath("/transfer");

  return {};
}

/** Iesirea din grup: se sterge propriul rand de participant (politica de DELETE). */
export async function iesiDinGrup(idGrup: number): Promise<RezultatMesaj> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabase
    .from("groups_participants")
    .delete()
    .eq("id_group", idGrup)
    .eq("id_user", user.id);

  if (error) {
    console.error("ERROR iesiDinGrup:", error);
    return { eroare: "Nu am putut ieși din grup. Încearcă din nou." };
  }

  revalidatePath("/grupuri");

  return {};
}
