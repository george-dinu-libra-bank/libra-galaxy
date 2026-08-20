"use client";

import { useEffect, useState } from "react";
import type { StarePlata } from "@/lib/plati";
import { createClient } from "@/lib/supabase/client";
import { abonareAutentificata } from "@/lib/supabase/realtime";

type Stare = { status: StarePlata | null; motiv: string | null };

const INITIALA: Stare = { status: null, motiv: null };

/**
 * Urmareste o SINGURA plata, dupa id.
 *
 * Filtrul se pune pe server (`id=eq.<uuid>`), deci ecranul de checkout nu vede
 * niciodata alte plati — iar RLS-ul din 0014_payments.sql se asigura ca nici
 * n-ar avea voie. Fara id (inca nu s-a creat plata) nu se deschide niciun canal.
 */
export function useStarePlata(idPlata: string | null): Stare {
  const [stare, setStare] = useState<Stare>(INITIALA);

  useEffect(() => {
    setStare(INITIALA);

    if (!idPlata) return;

    const supabase = createClient();
    let activ = true;

    const canal = supabase.channel(`plata:${idPlata}`).on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "payments",
        filter: `id=eq.${idPlata}`,
      },
      ({ new: rand }) => {
        const plata = rand as { status: StarePlata; motiv: string | null };
        setStare({ status: plata.status, motiv: plata.motiv });
      },
    );

    // Daca raspunsul vine intre crearea platii si abonare, mesajul se pierde. O
    // citire imediat dupa SUBSCRIBED inchide fereastra; un eveniment sosit intre
    // timp are prioritate, ca sa nu dam starea inapoi.
    const opreste = abonareAutentificata(supabase, canal, () => {
      void (async () => {
        const { data } = await supabase
          .from("payments")
          .select("status, motiv")
          .eq("id", idPlata)
          .maybeSingle();

        if (!activ || !data) return;

        setStare((curenta) =>
          curenta.status
            ? curenta
            : { status: data.status as StarePlata, motiv: data.motiv as string | null },
        );
      })();
    });

    return () => {
      activ = false;
      opreste();
    };
  }, [idPlata]);

  return stare;
}
