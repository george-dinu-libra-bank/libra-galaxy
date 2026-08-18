"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { supabaseConfigurat } from "@/lib/supabase/configurat";
import { genereazaIban } from "@/lib/iban";
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

  return process.env.NEXT_PUBLIC_SITE_URL ?? `${protocol}://${host}`;
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

  if (validEmail(email) || !date.parola)
    return { eroare: "Completeaza emailul si parola." };

  const supabase = await createClient();

  const { error } = await supabase.auth.signInWithPassword({
    email,
    password: date.parola,
  });

  if (error) return { eroare: traduEroare(error.message) };

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

  if (eroare) return { eroare };

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

  if (error) return { eroare: traduEroare(error.message) };

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

  if (eroare) return { eroare };

  const supabase = await createClient();

  const { error } = await supabase.auth.resetPasswordForEmail(adresa, {
    redirectTo: `${await origine()}/auth/callback?next=/dashboard`,
  });

  if (error) return { eroare: traduEroare(error.message) };

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
    await supabase.auth.signOut();
    revalidatePath("/", "layout");
  }

  redirect("/login");
}
