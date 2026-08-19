"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import {createAdminClient} from "@/lib/supabase/admin"
import type { StilCard } from "@/lib/data/carduri";

export type RezultatCard = { eroare?: string };

function generate16DigitNumber() {
  const randomPart = Math.floor(100000000000 + Math.random() * 900000000000);
  return `${randomPart}0022`;
}
function generate3DigitNumber() {
  return Math.floor(100 + Math.random() * 900);
}

export async function adaugaCard(cardStyle: StilCard): Promise<RezultatCard> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const numarCard = generate16DigitNumber();

  const now = new Date();
  const luna = String(now.getMonth() + 1).padStart(2, '0');
  const anul = String(now.getFullYear() + 3).slice(-2);

  const expiras_at = `${luna}/${anul}`;

  const ccv = generate3DigitNumber();

  const { error } = await supabaseAdmin
    .from("carduri")
    .insert({ 
      id_user: user.id, 
      card_style: cardStyle,
      numar_card:numarCard,
      data_expirare:expiras_at,
      ccv:ccv
     });

  if (error){
    console.error("ERROR adaugaCard: ",error)
 return { eroare: "Nu am putut crea cardul. Incearca din nou." };
  }
    

  revalidatePath("/dashboard");
  revalidatePath("/carduri");

  return {};
}

export type DateSensibileCard = { numar: string; ccv: string };
export type RezultatDateSensibile = { date?: DateSensibileCard; eroare?: string };

/**
 * Numarul complet si CCV-ul unui card propriu. Se cer doar dupa ce
 * utilizatorul confirma explicit in drawer — nu ajung niciodata in lista.
 */
export async function obtineDateSensibileCard(id: string): Promise<RezultatDateSensibile> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { data, error } = await supabaseAdmin
    .from("carduri")
    .select("numar_card, ccv")
    .eq("id", id)
    .eq("id_user", user.id)
    .maybeSingle();

  if (error || !data) return { eroare: "Nu am putut afisa datele cardului." };

  return {
    date: {
      numar: String(data.numar_card).replace(/(.{4})(?=.)/g, "$1 "),
      ccv: String(data.ccv),
    },
  };
}

/** Blocheaza/deblocheaza un card propriu. */
export async function comutaBlocareCard(id: string, blocat: boolean): Promise<RezultatCard> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { error } = await supabaseAdmin
    .from("carduri")
    .update({ is_blocked: blocat })
    .eq("id", id)
    .eq("id_user", user.id);

  if (error) return { eroare: "Nu am putut actualiza cardul." };

  revalidatePath("/dashboard");
  revalidatePath("/carduri");

  return {};
}
