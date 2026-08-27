"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";

/**
 * Popririle, dinspre analist.
 *
 * Rolul se verifica si aici, nu doar pe ecranul din care se apeleaza: o actiune
 * de server e un endpoint ca oricare altul. Backendul il verifica a doua oara,
 * iar RPC-urile din 0047 sunt acordate doar lui `service_role` — aceea e bariera
 * care conteaza.
 *
 * Mesajele de eroare vin traduse din backend (`MESAJE_POPRIRE` in
 * `routes/admin.py`), deci se arata ca atare: spun exact ce s-a oprit si de ce.
 */

export type RezultatPoprire = { eroare?: string };

function esec(eroare: unknown, implicit: string): RezultatPoprire {
  return {
    eroare: eroare instanceof BackendError ? eroare.message : implicit,
  };
}

export async function instituiePoprire(input: {
  idUtilizator: string;
  creditor: string;
  suma: number;
  dosar?: string;
  observatie?: string;
}): Promise<RezultatPoprire> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  if (!Number.isFinite(input.suma) || input.suma <= 0) {
    return { eroare: "Introdu o sumă validă." };
  }

  try {
    await backendFetch("api/v1/admin/popriri", admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_utilizator: input.idUtilizator,
        creditor: input.creditor.trim(),
        suma: input.suma,
        dosar: input.dosar?.trim() || null,
        observatie: input.observatie?.trim() || null,
      }),
    });
  } catch (eroare) {
    return esec(eroare, "Nu am putut institui poprirea. Încearcă din nou.");
  }

  revalidatePath("/admin/conturi");
  return {};
}

/** Fara suma, ia cat se poate acum — forma folosita in practica. */
export async function incaseazaPoprirea(
  idPoprire: string,
  suma?: number,
): Promise<RezultatPoprire> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/popriri/${idPoprire}/incaseaza`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suma: suma && suma > 0 ? suma : null }),
    });
  } catch (eroare) {
    return esec(eroare, "Nu am putut încasa poprirea. Încearcă din nou.");
  }

  revalidatePath("/admin/conturi");
  return {};
}

/**
 * Reverse-ul unei incasari: banii virati se intorc in contul clientului.
 *
 * NU ridica poprirea. Daca ea ramane activa, banii intorsi sunt din nou
 * indisponibili pe loc — datoria a redevenit neplatita. O poprire pusa gresit si
 * deja incasata se repara cu amandoua, in ordinea: intai stornare, apoi ridicare.
 */
export async function storneazaIncasarea(
  idPoprire: string,
  optiuni: { suma?: number; motiv?: string } = {},
): Promise<RezultatPoprire> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/popriri/${idPoprire}/storneaza`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        suma: optiuni.suma && optiuni.suma > 0 ? optiuni.suma : null,
        motiv: optiuni.motiv?.trim() || null,
      }),
    });
  } catch (eroare) {
    return esec(eroare, "Nu am putut storna încasarea. Încearcă din nou.");
  }

  revalidatePath("/admin/conturi");
  return {};
}

export async function ridicaPoprirea(
  idPoprire: string,
  motiv?: string,
): Promise<RezultatPoprire> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/admin/popriri/${idPoprire}/ridica`, admin.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motiv: motiv?.trim() || null }),
    });
  } catch (eroare) {
    return esec(eroare, "Nu am putut ridica poprirea. Încearcă din nou.");
  }

  revalidatePath("/admin/conturi");
  return {};
}
