"use server";

import { revalidatePath } from "next/cache";
import { BANCA_INTERNA, type BeneficiarTransfer } from "@/lib/data/transfer";
import { ibanEsteValid } from "@/lib/iban";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

export type RezultatCautareBeneficiar = { beneficiar?: BeneficiarTransfer; eroare?: string };
export type RezultatTransfer = { eroare?: string };

function normalizeazaIban(iban: string) {
  return iban.replace(/\s+/g, "").toUpperCase();
}

/** Rotunjeste la banut, ca sa nu ramana resturi din aritmetica in virgula mobila. */
function laBanut(valoare: number) {
  return Number(valoare.toFixed(2));
}

/** Cauta un cont Libra dupa IBAN, pentru drawerul „Beneficiar nou". */
export async function cautaBeneficiarDupaIban(
  ibanBrut: string,
): Promise<RezultatCautareBeneficiar> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const iban = normalizeazaIban(ibanBrut);

  if (!ibanEsteValid(iban)) return { eroare: "IBAN invalid." };

  const supabaseAdmin = createAdminClient();

  // IBAN-ul identifica un cont, nu un om (0007_conturi_bancare.sql).
  const { data, error } = await supabaseAdmin
    .from("conturi_bancare")
    .select("id, iban, id_user, profiles ( nume )")
    .eq("iban", iban)
    .maybeSingle();

  if (error) return { eroare: "Nu am putut cauta beneficiarul. Incearca din nou." };
  if (!data) return { eroare: "Nu exista niciun cont Libra cu acest IBAN." };

  const relatie = data.profiles as { nume: string } | { nume: string }[] | null;
  const proprietar = Array.isArray(relatie) ? relatie[0] : relatie;

  return {
    beneficiar: {
      id: data.id as string,
      // Un cont propriu ramane o destinatie valida: se pot muta bani intre
      // conturile aceleiasi persoane. Doar acelasi cont e respins, in RPC.
      nume: proprietar?.nume ?? "Cont Libra",
      iban: data.iban as string,
      banca: BANCA_INTERNA,
    },
  };
}

/**
 * Mesajele pentru utilizator, dupa codul ridicat de core_banking: functia pune
 * codul in `message`, iar textul lung in `details` (vezi 0004_core_banking.sql).
 */
const MESAJE_CORE_BANKING: Record<string, string> = {
  NEAUTENTIFICAT: "Trebuie sa fii autentificat.",
  NEAUTORIZAT: "Nu poti initia o plata in numele altui utilizator.",
  SUMA_INVALIDA: "Introdu o suma valida.",
  VALUTA_NESUPORTATA: "Momentan se pot trimite doar transferuri in RON.",
  IBAN_INVALID: "IBAN-ul beneficiarului este invalid.",
  BENEFICIAR_INEXISTENT: "Nu exista niciun cont Libra cu acest IBAN.",
  PROFIL_INEXISTENT: "Contul tau nu a fost gasit.",
  CONT_SURSA_INEXISTENT: "Contul din care vrei sa platesti nu exista.",
  CONT_SURSA_STRAIN: "Nu poti plati dintr-un cont care nu este al tau.",
  AUTOTRANSFER: "Nu poti trimite bani in acelasi cont din care platesti.",
  FONDURI_INSUFICIENTE: "Nu ai fonduri suficiente in cont.",
};

/**
 * Muta bani din contul propriu in contul beneficiarului (dupa IBAN) si scrie
 * tranzactia. Cardurile nu sunt implicate — soldul e pe cont.
 *
 * Toata logica bancara sta in functia public.core_banking
 * (0004_core_banking.sql): verificarile, debitarea, creditarea si istoricul se
 * fac intr-o singura tranzactie, cu lock pe randurile de profil — deci nu mai e
 * nevoie de pasi conditionati si rollback manual din TypeScript. Aici raman
 * doar validarile ieftine de formular si traducerea codurilor de eroare.
 */
export async function trimiteTransfer(input: {
  ibanDestinatar: string;
  suma: number;
  detalii: string;
  /** Contul din care se plateste; lipsa lui inseamna contul principal. */
  idContSursa?: string;
}): Promise<RezultatTransfer> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const suma = laBanut(input.suma);

  if (!Number.isFinite(suma) || suma <= 0) return { eroare: "Introdu o suma valida." };

  const iban = normalizeazaIban(input.ibanDestinatar);

  if (!ibanEsteValid(iban)) return { eroare: "IBAN-ul beneficiarului este invalid." };

  const supabaseAdmin = createAdminClient();

  const { error } = await supabaseAdmin.rpc("core_banking", {
    p_iban_dest: iban,
    p_suma: suma,
    p_descriere: input.detalii.trim() || null,
    p_id_cont_send: input.idContSursa ?? null,
    p_id_user: user.id,
  });

  if (error) {
    const mesaj = MESAJE_CORE_BANKING[error.message];

    // Orice altceva (functia lipseste, deadlock, retea) — log si mesaj generic.
    if (!mesaj) console.error("ERROR trimiteTransfer:", error);

    return { eroare: mesaj ?? "Nu am putut trimite banii. Incearca din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/carduri");
  revalidatePath("/istoric");
  revalidatePath("/transfer");

  return {};
}
