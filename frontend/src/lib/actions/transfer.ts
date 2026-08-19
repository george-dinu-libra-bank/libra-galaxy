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

  const { data, error } = await supabaseAdmin
    .from("profiles")
    .select("id, nume, iban_cont")
    .eq("iban_cont", iban)
    .maybeSingle();

  if (error) return { eroare: "Nu am putut cauta beneficiarul. Incearca din nou." };
  if (!data) return { eroare: "Nu exista niciun cont Libra cu acest IBAN." };
  if (data.id === user.id) return { eroare: "Nu poti trimite bani catre propriul cont." };

  return {
    beneficiar: {
      id: data.id as string,
      nume: data.nume as string,
      iban: data.iban_cont as string,
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
  DESTINATIE_INVALIDA: "IBAN-ul beneficiarului este invalid.",
  CARD_SURSA_LIPSA: "Alege cardul din care trimiti banii.",
  CARD_SURSA_INVALID: "Cardul din care trimiti nu a fost gasit.",
  CARD_BLOCAT: "Cardul selectat este blocat.",
  CARD_EXPIRAT: "Cardul selectat este expirat.",
  BENEFICIAR_INEXISTENT: "Nu exista niciun cont Libra cu acest IBAN.",
  BENEFICIAR_FARA_CARD: "Beneficiarul nu are un card activ.",
  CARD_DEST_INEXISTENT: "Nu exista niciun card cu datele introduse.",
  CARD_DEST_BLOCAT: "Cardul beneficiarului este blocat si nu poate primi bani.",
  AUTOTRANSFER: "Nu poti trimite bani catre propriul cont.",
  FONDURI_INSUFICIENTE: "Nu ai fonduri suficiente in cardul selectat.",
};

/**
 * Muta bani dintr-un card propriu in cardul beneficiarului si scrie tranzactia.
 *
 * Toata logica bancara sta in functia public.core_banking
 * (0004_core_banking.sql): verificarile, debitarea, creditarea si istoricul se
 * fac intr-o singura tranzactie, cu lock pe randurile de card — deci nu mai e
 * nevoie de pasi conditionati si rollback manual din TypeScript. Aici raman
 * doar validarile ieftine de formular si traducerea codurilor de eroare.
 */
export async function trimiteTransfer(input: {
  idCardSursa: string;
  ibanDestinatar: string;
  suma: number;
  detalii: string;
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
    p_id_card_send: input.idCardSursa,
    p_suma: suma,
    p_iban_dest: iban,
    p_descriere: input.detalii.trim() || null,
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
