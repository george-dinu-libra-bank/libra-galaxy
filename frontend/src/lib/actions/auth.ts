"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { SITE_URL, supabaseConfigurat } from "@/lib/env";
import { genereazaIban } from "@/lib/iban";
import {
  inregistreazaSelfieReferinta,
  verificaIdentitateInregistrare,
  verificaLoginFata,
} from "@/lib/actions/identitate";
import {
  normalizeazaTelefon,
  validCnp,
  validEmail,
  validNume,
  validParola,
  validTelefon,
} from "@/lib/validare";

export type RezultatAuth = {
  eroare?: string;
  /** Mesaj de succes afisat in loc de redirect (ex. confirmare pe email). */
  mesaj?: string;
};

/** Traduce erorile Supabase in mesaje utile in romana. */
function traduEroare(mesaj: string): string {
  const m = mesaj.toLowerCase();

  if (m.includes("invalid login credentials"))
    return "Email sau parola gresita.";
  if (m.includes("email not confirmed"))
    return "Contul nu este confirmat. Verifica emailul primit de la noi.";
  if (m.includes("user already registered") || m.includes("already been registered"))
    return "Exista deja un cont cu aceasta adresa de email.";
  if (m.includes("email rate limit") || m.includes("rate limit"))
    return "Prea multe incercari. Reia peste cateva minute.";
  if (m.includes("profiles_cnp_key") || m.includes("cnp"))
    return "Exista deja un cont inregistrat cu acest CNP.";
  if (m.includes("database error"))
    return "Nu am putut crea profilul. Verifica datele introduse si incearca din nou.";

  return "A aparut o eroare. Incearca din nou.";
}

async function origine() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const protocol = h.get("x-forwarded-proto") ?? "http";

  if (!SITE_URL && !host)
    console.error("[auth/origine] lipseste NEXT_PUBLIC_SITE_URL si headerul host");

  return SITE_URL ?? `${protocol}://${host}`;
}

/* -------------------------------------------------------------------------- */
/* Autentificare                                                               */
/* -------------------------------------------------------------------------- */

export async function autentifica(date: {
  email: string;
  parola: string;
  redirectTo?: string;
}): Promise<RezultatAuth> {
  const email = date.email.trim().toLowerCase();

  if (validEmail(email) || !date.parola) {
    console.error("[auth/autentifica] date incomplete", { email });
    return { eroare: "Completeaza emailul si parola." };
  }

  const supabase = await createClient();

  const { error } = await supabase.auth.signInWithPassword({
    email,
    password: date.parola,
  });

  if (error) {
    console.error("[auth/autentifica] signInWithPassword", {
      email,
      status: error.status,
      code: error.code,
      message: error.message,
    });
    return { eroare: traduEroare(error.message) };
  }

  revalidatePath("/", "layout");
  redirect(date.redirectTo || "/dashboard");
}

/* -------------------------------------------------------------------------- */
/* Autentificare biometrica                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Login fara parola: un cadru live de la camera e comparat de backend cu
 * selfie-ul 'verified' salvat la inregistrare (verificaLoginFata). Doar la
 * potrivire cream o sesiune reala — Supabase nu ofera din oficiu "logheaza
 * userul X pe incredere", asa ca folosim Admin API sa generam un magic link
 * (fara sa trimitem vreun email) si il "consumam" imediat cu verifyOtp pe
 * clientul cu cookie-uri, ceea ce seteaza sesiunea la fel ca orice alt login.
 *
 * E gandit ca alternativa la parola, nu ca al doilea factor — daca vrem 2FA
 * real (parola + fata), fluxul trebuie schimbat sa ceara ambele.
 */
export async function autentificaFata(date: {
  email: string;
  imagineLive: File;
  redirectTo?: string;
}): Promise<RezultatAuth> {
  const email = date.email.trim().toLowerCase();

  if (validEmail(email)) {
    return { eroare: "Introdu emailul contului inainte de a folosi biometria." };
  }
  if (!(date.imagineLive instanceof File) || date.imagineLive.size === 0) {
    return { eroare: "Nu am primit nicio poza de la camera." };
  }

  const potrivit = await verificaLoginFata(email, date.imagineLive);

  if (!potrivit) {
    return { eroare: "Nu am putut confirma identitatea. Incearca din nou, cu lumina mai buna, sau foloseste parola." };
  }

  const supabaseAdmin = await createAdminClient();

  const { data, error } = await supabaseAdmin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });

  if (error || !data?.properties?.hashed_token) {
    console.error("[auth/autentificaFata] generateLink", { email, error });
    return { eroare: "Nu am putut finaliza autentificarea. Incearca din nou." };
  }

  const supabase = await createClient();

  // token_hash, nu token+email: hashed_token din generateLink se consuma cu
  // parametrul token_hash — trimis ca "token" alaturi de email (cum arata
  // multe exemple neoficiale), GoTrue il trateaza gresit ca pe un cod OTP
  // scurt introdus manual si raspunde generic "expired or invalid".
  const { error: eroareOtp } = await supabase.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: (data.properties.verification_type ?? "magiclink") as "magiclink" | "email",
  });

  if (eroareOtp) {
    console.error("[auth/autentificaFata] verifyOtp", { email, eroareOtp });
    return { eroare: "Nu am putut finaliza autentificarea. Incearca din nou." };
  }

  revalidatePath("/", "layout");
  redirect(date.redirectTo || "/dashboard");
}

/* -------------------------------------------------------------------------- */
/* Inregistrare                                                                */
/* -------------------------------------------------------------------------- */

export async function inregistreaza(date: {
  nume: string;
  cnp: string;
  telefon: string;
  email: string;
  parola: string;
  buletin: File | null;
  selfie: File;
}): Promise<RezultatAuth> {
  const nume = date.nume.trim().replace(/\s+/g, " ");
  const cnp = date.cnp.replace(/\s+/g, "");
  const telefon = normalizeazaTelefon(date.telefon);
  const email = date.email.trim().toLowerCase();

  // Aceleasi validari ca in client — clientul poate fi ocolit.
  const eroare =
    validNume(nume) ||
    validCnp(cnp) ||
    validTelefon(telefon) ||
    validEmail(email) ||
    validParola(date.parola);

  if (eroare) {
    console.error("[auth/inregistreaza] validare esuata", { email, eroare });
    return { eroare };
  }

  if (!(date.selfie instanceof File) || date.selfie.size === 0) {
    return { eroare: "Fa un selfie ca sa iti confirmam identitatea." };
  }

  const supabase = await createClient();

  // IBAN-ul contului curent se genereaza pe server, nu in browser, si ajunge
  // in user_metadata; trigger-ul on_auth_user_created il copiaza in profiles.
  const iban_cont = genereazaIban();

  const { data, error } = await supabase.auth.signUp({
    email,
    password: date.parola,
    options: {
      emailRedirectTo: `${await origine()}/auth/callback`,
      data: { nume, cnp, telefon, iban_cont },
    },
  });

  if (error) {
    console.error("[auth/inregistreaza] signUp", {
      email,
      status: error.status,
      code: error.code,
      message: error.message,
    });
    return { eroare: traduEroare(error.message) };
  }

  // Verificarea identitatii (OCR + DeepFace) nu trebuie sa blocheze crearea
  // contului — un scor mic sau un serviciu picat inseamna doar
  // verification_status = 'pending'/'pending_review', nu esec la inregistrare.
  // Fara buletin (userul a ales sa-l trimita mai tarziu): doar selfie-ul se
  // retine, ca reper pentru trimiteBuletinUlterior().
  if (data.user) {
    if (date.buletin) {
      await verificaIdentitateInregistrare(data.user.id, date.buletin, date.selfie, cnp);
    } else {
      await inregistreazaSelfieReferinta(data.user.id, date.selfie);
    }
  }

  // Fara sesiune => in proiectul Supabase e activata confirmarea pe email.
  if (!data.session) {
    return {
      mesaj: `Ti-am trimis un email de confirmare la ${email}. Deschide linkul ca sa iti activam contul.`,
    };
  }

  revalidatePath("/", "layout");
  redirect("/dashboard");
}

/* -------------------------------------------------------------------------- */
/* Resetare parola                                                             */
/* -------------------------------------------------------------------------- */

export async function trimiteResetareParola(email: string): Promise<RezultatAuth> {
  const adresa = email.trim().toLowerCase();
  const eroare = validEmail(adresa);

  if (eroare) {
    console.error("[auth/trimiteResetareParola] email invalid", { adresa, eroare });
    return { eroare };
  }

  const supabase = await createClient();

  const { error } = await supabase.auth.resetPasswordForEmail(adresa, {
    redirectTo: `${await origine()}/auth/callback?next=/dashboard`,
  });

  if (error) {
    console.error("[auth/trimiteResetareParola] resetPasswordForEmail", {
      adresa,
      status: error.status,
      code: error.code,
      message: error.message,
    });
    return { eroare: traduEroare(error.message) };
  }

  return {
    mesaj: `Daca exista un cont pentru ${adresa}, vei primi un email cu instructiuni de resetare.`,
  };
}

/* -------------------------------------------------------------------------- */
/* Deconectare                                                                 */
/* -------------------------------------------------------------------------- */

export async function deconecteaza() {
  if (supabaseConfigurat) {
    const supabase = await createClient();
    const { error } = await supabase.auth.signOut();

    if (error) {
      console.error("[auth/deconecteaza] signOut", {
        status: error.status,
        code: error.code,
        message: error.message,
      });
    }

    revalidatePath("/", "layout");
  }

  redirect("/login");
}
