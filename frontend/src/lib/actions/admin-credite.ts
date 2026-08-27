"use server";

import { revalidatePath } from "next/cache";
import { checkAdmin } from "@/lib/admin";
import { backendFetch, BackendError } from "@/lib/backend";
import type { ActiuneAnalist, ContractCerere, DosarCredit } from "@/lib/tipuri-admin";

export type RezultatDecizieCredit = { eroare?: string; status?: string };

/**
 * Verificarea de rol se face si aici, nu doar pe ecranul din care se apeleaza:
 * o actiune de server e un endpoint ca oricare altul, care poate fi chemat
 * direct. Backendul o verifica a treia oara — aia e cea care conteaza.
 */
async function cuAdmin<T>(
  apel: (token: string) => Promise<T>,
): Promise<{ date?: T; eroare?: string }> {
  const admin = await checkAdmin();
  if (!admin) return { eroare: "Nu ai dreptul sa faci asta." };

  try {
    return { date: await apel(admin.token) };
  } catch (eroare) {
    if (eroare instanceof BackendError) return { eroare: eroare.message };
    return { eroare: "Nu am putut trimite cererea. Încearcă din nou." };
  }
}

/**
 * Ce face analistul cu un dosar aflat in lucru.
 *
 * Patru actiuni, un singur endpoint. `aproba` NU acorda creditul — genereaza
 * oferta, pe care clientul o semneaza el, din aplicatie. `cere_documente` si
 * `notifica` cer un mesaj: el e tot ce vede clientul.
 */
export async function decideCerereCredit(
  idCerere: string,
  actiune: ActiuneAnalist,
  nota?: string,
): Promise<RezultatDecizieCredit> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<{ status: string }>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/decizie`,
      token,
      { method: "POST", body: JSON.stringify({ actiune, nota: nota?.trim() || null }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath("/admin/credite");
  revalidatePath(`/admin/credite/${idCerere}`);
  return { status: rezultat.date?.status };
}

/**
 * Valideaza cifra citita din adeverinta.
 *
 * Analistul completeaza o intrare a motorului de scoring, nu alege un rezultat:
 * dupa confirmare ruleaza acelasi calcul determinist, cu venitul in plus. De
 * aceea scorul se poate schimba imediat, fara ca nimeni sa fi apasat „aproba".
 */
export async function confirmaVenitDinAdeverinta(
  idDocument: string,
  idCerere: string,
  venitConfirmat: string,
): Promise<RezultatDecizieCredit> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<{ cerere: { status: string } }>(
      `api/v1/admin/credite/documente/${encodeURIComponent(idDocument)}/confirma`,
      token,
      { method: "POST", body: JSON.stringify({ venit_confirmat: venitConfirmat }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath("/admin/credite");
  revalidatePath(`/admin/credite/${idCerere}`);
  return { status: rezultat.date?.cerere.status };
}

/**
 * Raspunsul analistului in fir, fara sa fie o decizie.
 *
 * Cele patru actiuni din `decideCerereCredit` isi scriu si ele textul in acelasi
 * fir; asta e pentru cand nu e nimic de decis, doar de raspuns.
 */
export async function raspundeInFir(
  idCerere: string,
  text: string,
): Promise<{ eroare?: string }> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<Record<string, unknown>>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/mesaje`,
      token,
      { method: "POST", body: JSON.stringify({ text }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath(`/admin/credite/${idCerere}`);
  return {};
}


export type RezultatRulareAi = { eroare?: string; dosar?: DosarCredit };

/**
 * "Ruleaza din nou" — spre deosebire de catch-up-ul lazy de la deschiderea
 * dosarului, recheama efectiv modelul (backend: `forta=True`), sincron, ca
 * analistul sa vada imediat rezultatul.
 */
export async function ruleazaPipelineAi(idCerere: string): Promise<RezultatRulareAi> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<DosarCredit>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/ai`,
      token,
      { method: "POST" },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath("/admin/credite");
  revalidatePath(`/admin/credite/${idCerere}`);
  return { dosar: rezultat.date };
}


export type RezultatContract = { eroare?: string; contract?: ContractCerere };

/**
 * Salveaza contractul editat de analist.
 *
 * HTML-ul pleaca asa cum l-a produs editorul; backendul il taie la lista de
 * etichete permise inainte sa il scrie (`credit/contract.py:sanitizeaza`).
 * Nu incercam sa sanitizam si aici: doua liste de etichete care trebuie tinute
 * in acord sunt o promisiune pe care n-o poate respecta nimeni.
 */
export async function salveazaContract(
  idCerere: string,
  html: string,
): Promise<RezultatContract> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<ContractCerere>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/contract`,
      token,
      { method: "PUT", body: JSON.stringify({ html }) },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath(`/admin/credite/${idCerere}`);
  return { contract: rezultat.date };
}

/**
 * Reface contractul din sablon, cu datele de acum.
 *
 * Arunca ce a scris analistul, deci ecranul cere o confirmare inainte. Util mai
 * ales dupa ce cererea primeste rata si DAE: sablonul generat la depunere avea
 * liniute in locul lor.
 */
export async function regenereazaContract(idCerere: string): Promise<RezultatContract> {
  const rezultat = await cuAdmin((token) =>
    backendFetch<ContractCerere>(
      `api/v1/admin/credite/cereri/${encodeURIComponent(idCerere)}/contract/regenereaza`,
      token,
      { method: "POST" },
    ),
  );

  if (rezultat.eroare) return { eroare: rezultat.eroare };

  revalidatePath(`/admin/credite/${idCerere}`);
  return { contract: rezultat.date };
}
