"use server";

import { BACKEND_INTERNAL_API_KEY as CHEIE_INTERNA, BACKEND_INTERNAL_URL as BACKEND_URL } from "@/lib/env";
import { createAdminClient } from "../supabase/admin";

/**
 * Verificarea identitatii (OCR buletin + comparare fete cu DeepFace) traieste
 * intr-un serviciu FastAPI separat — vezi ARCHITECTURE.md §3.4 si backend/.
 * BACKEND_URL e o variabila server-only (nu NEXT_PUBLIC_): apelurile pornesc
 * mereu din server actions, niciodata direct din browser.
 */
const MAX_OCTETI_BULETIN = 8 * 1024 * 1024;

/**
 * Backend-ul raspunde la orice eroare cu plicul standard
 * {"success": false, "error": {"code": "...", "message": "..."}} (vezi
 * backend/app/core/errors.py si envelope.py) — un cod stabil de diagnostic,
 * nu doar un status HTTP gol. Validarea automata FastAPI (422, cerere
 * malformata) ocoleste plicul si raspunde cu {"detail": "..."} — tratata
 * separat mai jos. Cand nu putem parsa raspunsul deloc (backend-ul e complet
 * picat), cazul e tot logat, doar cu cod generic.
 */
async function citesteEroare(raspuns: Response): Promise<{ cod: string; mesaj: string }> {
  try {
    const corp = (await raspuns.json()) as {
      error?: { code?: string; message?: string };
      detail?: string;
    };
    if (corp.error?.code) return { cod: corp.error.code, mesaj: corp.error.message ?? "" };
    if (typeof corp.detail === "string") return { cod: "eroare_http", mesaj: corp.detail };
  } catch {
    // corpul nu era JSON — backend-ul probabil a picat complet
  }
  return { cod: `http_${raspuns.status}`, mesaj: raspuns.statusText };
}

export type RezultatExtragereCnp = { cnp?: string; incredere?: number; eroare?: string };

/**
 * Trimite poza buletinului la serviciul de OCR. Se apeleaza inainte de a
 * exista un cont (nu are sens sa ceri autentificare pentru asta), deci
 * ruta din backend nu verifica un token — vezi backend/app/api/routes/identity.py.
 */
export async function extrageCnp(formData: FormData): Promise<RezultatExtragereCnp> {
  const poza = formData.get("buletin");

  if (!(poza instanceof File) || poza.size === 0) {
    return { eroare: "Alege o poza a buletinului." };
  }
  if (poza.size > MAX_OCTETI_BULETIN) {
    return { eroare: "Poza este prea mare (maxim 8 MB)." };
  }

  try {
    const trimitere = new FormData();
    trimitere.append("buletin", poza, poza.name || "buletin.jpg");

    const raspuns = await fetch(`${BACKEND_URL}/api/identity/extract-cnp`, {
      method: "POST",
      body: trimitere,
    });

    if (!raspuns.ok) {
      const { cod, mesaj } = await citesteEroare(raspuns);
      console.error("[identitate/extrageCnp]", { status: raspuns.status, cod, mesaj });
      return { eroare: "Nu am putut citi CNP-ul din poza. Încearcă o poza mai clara." };
    }

    const date = (await raspuns.json()) as { cnp: string | null; confidence: number };

    if (!date.cnp) {
      return { eroare: "Nu am putut citi CNP-ul din poza. Încearcă o poza mai clara." };
    }

    return { cnp: date.cnp, incredere: date.confidence };
  } catch (eroare) {
    console.error("[identitate/extrageCnp] cod=fetch_esuat — backend-ul nu raspunde deloc?", eroare);
    return { eroare: "Serviciul de verificare nu raspunde momentan. Încearcă din nou." };
  }
}

export type StatusVerificare = "verified" | "pending_review" | "eroare";

/**
 * Urca poza buletinului si selfie-ul in bucket-urile private si cere
 * serviciului FastAPI sa compare fetele (DeepFace/ArcFace). Se apeleaza din
 * inregistreaza() imediat dupa signUp(), inainte de orice redirect.
 *
 * Foloseste service-role (ca la avatare/carduri) si autentificarea "cheie
 * interna" fata de FastAPI: daca proiectul are confirmarea pe email
 * activata, inca nu exista o sesiune a userului in acest moment, deci nu
 * avem un JWT de trimis. Serverul Next.js e insusi contextul de incredere
 * in aceasta fereastra ingusta (vezi backend/app/api/dependencies.py).
 *
 * Nu arunca — un esec aici nu trebuie sa blocheze crearea contului. Statusul
 * ramane 'pending' pe profil si poate fi tratat ulterior (reincercare sau
 * revizuire manuala, in admin panel-ul viitor). Fiecare cale de esec e
 * logata cu un cod distinct, ca sa se stie exact ce a picat fara sa mai
 * sapi in logurile backend-ului.
 */
export async function verificaIdentitateInregistrare(
  userId: string,
  buletin: File,
  selfie: File,
  cnpExtras: string,
): Promise<StatusVerificare> {
  if (!CHEIE_INTERNA) {
    console.error("[identitate/verificaIdentitateInregistrare] cod=lipseste_cheie_interna — completeaza BACKEND_INTERNAL_API_KEY in frontend/.env");
    return "eroare";
  }

  let supabaseAdmin: Awaited<ReturnType<typeof createAdminClient>>;
  try {
    supabaseAdmin = await createAdminClient();
  } catch (eroare) {
    console.error("[identitate/verificaIdentitateInregistrare] cod=admin_client_esuat", eroare);
    return "eroare";
  }

  const caleBuletin = `${userId}/buletin-${Date.now()}.jpg`;
  const caleSelfie = `${userId}/selfie-${Date.now()}.jpg`;

  const [incarcareBuletin, incarcareSelfie] = await Promise.all([
    supabaseAdmin.storage
      .from("buletine")
      .upload(caleBuletin, buletin, { contentType: buletin.type || "image/jpeg", upsert: false }),
    supabaseAdmin.storage
      .from("selfie-uri")
      .upload(caleSelfie, selfie, { contentType: selfie.type || "image/jpeg", upsert: false }),
  ]);

  if (incarcareBuletin.error || incarcareSelfie.error) {
    console.error("[identitate/verificaIdentitateInregistrare] cod=upload_storage_esuat", {
      buletin: incarcareBuletin.error?.message,
      selfie: incarcareSelfie.error?.message,
    });
    return "eroare";
  }

  try {
    const raspuns = await fetch(`${BACKEND_URL}/api/identity/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Api-Key": CHEIE_INTERNA,
        "X-User-Id": userId,
      },
      body: JSON.stringify({
        user_id: userId,
        buletin_path: caleBuletin,
        selfie_path: caleSelfie,
        extracted_cnp: cnpExtras,
      }),
    });

    if (!raspuns.ok) {
      const { cod, mesaj } = await citesteEroare(raspuns);
      console.error("[identitate/verificaIdentitateInregistrare] verify a esuat", {
        status: raspuns.status,
        cod,
        mesaj,
      });
      return "eroare";
    }

    const date = (await raspuns.json()) as { status: "verified" | "pending_review" };
    return date.status;
  } catch (eroare) {
    console.error("[identitate/verificaIdentitateInregistrare] cod=fetch_esuat — backend-ul nu raspunde deloc?", eroare);
    return "eroare";
  }
}

/**
 * Login biometric: trimite un cadru live de la camera + emailul introdus,
 * ca backend-ul sa-l compare 1:1 cu ultimul selfie 'verified' al contului
 * (vezi backend/app/services/identity_service.py verifica_login_fata).
 * Fara autentificare (userul inca nu are sesiune) — protejata prin rate
 * limiting pe email+IP in backend (backend/app/infrastructure/rate_limit.py).
 *
 * Raspunsul e strict boolean; sesiunea reala se creeaza separat, in
 * autentificaFata() din auth.ts, doar daca matched === true.
 */
export async function verificaLoginFata(email: string, imagineLive: File): Promise<boolean> {
  try {
    const trimitere = new FormData();
    trimitere.append("email", email);
    trimitere.append("imagine", imagineLive, imagineLive.name || "live.jpg");

    const raspuns = await fetch(`${BACKEND_URL}/api/identity/login-match`, {
      method: "POST",
      body: trimitere,
    });

    if (!raspuns.ok) {
      const { cod, mesaj } = await citesteEroare(raspuns);
      console.error("[identitate/verificaLoginFata]", { status: raspuns.status, cod, mesaj });
      return false;
    }

    const date = (await raspuns.json()) as { matched: boolean };
    return date.matched;
  } catch (eroare) {
    console.error("[identitate/verificaLoginFata] cod=fetch_esuat — backend-ul nu raspunde deloc?", eroare);
    return false;
  }
}
