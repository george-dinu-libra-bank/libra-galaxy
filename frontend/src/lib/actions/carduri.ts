"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import {createAdminClient} from "@/lib/supabase/admin"
import type { StilCard, TipCard } from "@/lib/data/carduri";

export type RezultatCard = { eroare?: string };

/**
 * Un numar de card de 16 cifre, valid Luhn.
 *
 * Varianta de dinainte lipea un sufix fix — `${aleator}0022` — asa ca TOATE
 * cardurile din baza se terminau in 0022. Ultimele patru cifre sunt insa exact
 * ce vede omul cand confirma o plata („Card •••• 0022"), iar acum, cand fiecare
 * card plateste din alt cont, doua carduri identice la afisare inseamna ca nu
 * poti sti din ce cont pleaca banii.
 *
 * Cifra de control Luhn nu e ceruta de baza (constrangerea verifica doar 16
 * cifre), dar e ce documenteaza schema si ce valideaza orice formular de
 * checkout serios.
 */
function genereazaNumarCard(): string {
  const cifre = Array.from({ length: 15 }, () => Math.floor(Math.random() * 10));

  // Luhn: se dubleaza fiecare a doua cifra pornind din dreapta, iar rezultatele
  // peste 9 se reduc scazand 9. Cifra de control aduce totalul la un multiplu de 10.
  let suma = 0;
  cifre.forEach((cifra, i) => {
    // Cu 15 cifre si cifra de control pe pozitia 16, indicii pari se dubleaza.
    const dublata = i % 2 === 0 ? cifra * 2 : cifra;
    suma += dublata > 9 ? dublata - 9 : dublata;
  });

  const control = (10 - (suma % 10)) % 10;
  return cifre.join("") + String(control);
}

function genereazaCcv(): string {
  return String(Math.floor(100 + Math.random() * 900));
}

export async function adaugaCard(
  cardStyle: StilCard,
  idCont: string,
  tip: TipCard = "fizic",
): Promise<RezultatCard> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };
  if (!idCont) return { eroare: "Alege contul din care va plati cardul." };

  // Contul trebuie sa fie al lui. Verificarea e obligatorie aici, nu optionala:
  // inserarea merge cu service_role, care ocoleste RLS, deci baza nu ne mai
  // apara de un id de cont strain trimis din afara formularului.
  const { data: cont } = await supabaseAdmin
    .from("conturi_bancare")
    .select("id")
    .eq("id", idCont)
    .eq("id_user", user.id)
    .maybeSingle();

  if (!cont) return { eroare: "Contul ales nu este al tau." };

  const numarCard = genereazaNumarCard();

  const now = new Date();
  const luna = String(now.getMonth() + 1).padStart(2, "0");
  const anul = String(now.getFullYear() + 3).slice(-2);

  const expiras_at = `${luna}/${anul}`;

  const ccv = genereazaCcv();

  const { error } = await supabaseAdmin.from("carduri").insert({
    id_user: user.id,
    id_cont: idCont,
    card_style: cardStyle,
    tip,
    numar_card: numarCard,
    data_expirare: expiras_at,
    ccv: ccv,
  });

  if (error) {
    console.error("ERROR adaugaCard: ", error);
    return { eroare: "Nu am putut crea cardul. Incearca din nou." };
  }

  revalidatePath("/dashboard");
  revalidatePath("/carduri");

  return {};
}

/**
 * Limita zilnica a unui card propriu, in valuta contului.
 *
 * `null` sterge limita. Verificarea se face in `aproba_plata` (0031, mutata
 * acolo de 0044), nu aici: o limita aparata doar de interfata n-ar fi o limita.
 */
export async function seteazaLimitaCard(
  id: string,
  limita: number | null,
): Promise<RezultatCard> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  if (limita !== null && (!Number.isFinite(limita) || limita <= 0)) {
    return { eroare: "Limita trebuie sa fie un numar mai mare decat zero." };
  }

  const { error } = await supabaseAdmin
    .from("carduri")
    .update({ limita_zilnica: limita })
    .eq("id", id)
    .eq("id_user", user.id);

  if (error) return { eroare: "Nu am putut salva limita." };

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

/**
 * Blocheaza sau deblocheaza un card propriu.
 *
 * Scrie doar `is_blocked`, steagul clientului. `blocat_administrativ` — masura
 * bancii — nu e atins niciodata de aici, iar un card oprit de banca nu poate fi
 * repornit din aplicatie: altfel orice masura ar tine pana la prima apasare a
 * celui vizat de ea.
 *
 * Verificarea de mai jos e o comoditate, ca omul sa primeasca un mesaj clar.
 * Bariera adevarata e in `aproba_plata` (0032, mutata acolo de 0044), care
 * refuza orice plata pe un card blocat de banca, indiferent ce scrie in
 * `is_blocked`.
 */
export async function comutaBlocareCard(id: string, blocat: boolean): Promise<RezultatCard> {
  const supabase = await createClient();
  const supabaseAdmin = await createAdminClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { data: card } = await supabaseAdmin
    .from("carduri")
    .select("blocat_administrativ")
    .eq("id", id)
    .eq("id_user", user.id)
    .maybeSingle();

  if (!card) return { eroare: "Cardul nu a fost gasit." };

  if (card.blocat_administrativ && !blocat) {
    return {
      eroare:
        "Cardul a fost blocat de bancă și nu poate fi deblocat din aplicație. Contactează suportul.",
    };
  }

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
