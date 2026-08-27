"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";
import { apelBackend } from "@/lib/data/backend";
import type { Investigatie, RezultatInvestigatie } from "@/lib/data/investigatii";

/**
 * Acțiunile administratorului și ale clientului pe o investigație de fraudă.
 *
 * Rolul se verifică și aici, nu doar pe ecranul din care se apelează: o acțiune
 * de server e un endpoint ca oricare altul. Backendul îl verifică din nou —
 * aceea e bariera care contează.
 */

export type Rezultat<T = void> = { date?: T; eroare?: string };

function mesajEroare(exc: unknown, implicit: string): string {
  return exc instanceof BackendError ? exc.message : implicit;
}

// -- administratorul ----------------------------------------------------------

export type TranzactieDeLegat = { id_tranzactie: string; motiv?: string };

export async function deschideInvestigatie(
  idUtilizator: string,
  motiv: string,
  gravitate: number | null,
  numarSemnalari: number | null,
  tranzactii: TranzactieDeLegat[] = [],
): Promise<Rezultat<Investigatie>> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    const caz = await backendFetch<Investigatie>("api/v1/cazuri", admin.token, {
      method: "POST",
      body: JSON.stringify({
        id_utilizator: idUtilizator,
        motiv,
        gravitate: gravitate,
        numar_semnalari: numarSemnalari,
        tranzactii,
      }),
    });

    revalidatePath("/admin/investigatii");
    return { date: caz };
  } catch (exc) {
    return { eroare: mesajEroare(exc, "Nu am putut deschide investigația.") };
  }
}

export type MesajPropus = {
  text: string;
  intrebari: string[];
  scris_de_agent: boolean;
};

/**
 * Cere redactorului un text. Nu trimite nimic și nu scrie nimic în dosar.
 *
 * `scris_de_agent: false` cu text gol nu e o eroare: înseamnă că agentul nu e
 * configurat sau n-a putut scrie, iar administratorul compune el mesajul.
 */
export async function pregatesteMesaj(
  idCaz: string,
  intrebari: string[],
  nota = "",
): Promise<Rezultat<MesajPropus>> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    const propus = await backendFetch<MesajPropus>(
      `api/v1/cazuri/${encodeURIComponent(idCaz)}/pregateste`,
      admin.token,
      { method: "POST", body: JSON.stringify({ intrebari, nota }) },
    );
    return { date: propus };
  } catch (exc) {
    return { eroare: mesajEroare(exc, "Nu am putut pregăti mesajul.") };
  }
}

export async function trimiteMesaj(
  idCaz: string,
  text: string,
  intrebari: string[],
  propusDeAgent: boolean,
  editatDeOm: boolean,
): Promise<Rezultat> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/cazuri/${encodeURIComponent(idCaz)}/mesaje`, admin.token, {
      method: "POST",
      body: JSON.stringify({
        text,
        intrebari,
        propus_de_agent: propusDeAgent,
        editat_de_om: editatDeOm,
      }),
    });

    revalidatePath(`/admin/investigatii/${idCaz}`);
    revalidatePath("/admin/investigatii");
    return {};
  } catch (exc) {
    return { eroare: mesajEroare(exc, "Nu am putut trimite mesajul.") };
  }
}

/**
 * Consemnează urmarea aleasă de administrator.
 *
 * Nu blochează și nu deblochează nimic — nici măcar `deblocat`, care doar scrie
 * ce a decis omul. Deblocarea propriu-zisă rămâne butonul din ecranul contului.
 */
export async function inchideInvestigatie(
  idCaz: string,
  rezultat: RezultatInvestigatie,
  nota = "",
): Promise<Rezultat> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul să faci asta." };

  try {
    await backendFetch(`api/v1/cazuri/${encodeURIComponent(idCaz)}/inchide`, admin.token, {
      method: "POST",
      body: JSON.stringify({ rezultat, nota }),
    });

    revalidatePath(`/admin/investigatii/${idCaz}`);
    revalidatePath("/admin/investigatii");
    return {};
  } catch (exc) {
    return { eroare: mesajEroare(exc, "Nu am putut închide investigația.") };
  }
}

// -- clientul -----------------------------------------------------------------

export async function raspundeInvestigatie(
  idCaz: string,
  text: string,
): Promise<Rezultat> {
  const { eroare } = await apelBackend(`/api/v1/cazuri/${encodeURIComponent(idCaz)}/raspunde`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (eroare) return { eroare };

  revalidatePath(`/investigatii/${idCaz}`);
  return {};
}
