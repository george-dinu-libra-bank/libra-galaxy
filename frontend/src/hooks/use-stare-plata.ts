"use client";

import { useEffect, useState } from "react";
import type { StarePlata } from "@/lib/plati";
import { createClient } from "@/lib/supabase/client";
import { abonareAutentificata } from "@/lib/supabase/realtime";

type Stare = { status: StarePlata | null; motiv: string | null };

const INITIALA: Stare = { status: null, motiv: null };

/**
 * Urmareste o SINGURA plata, dupa id, pe ecranul de checkout al magazinului.
 *
 * Canalul e broadcast, nu `postgres_changes`: de la 0035_plata_dupa_card.sql
 * incoace, cine cumpara nu e neaparat posesorul cardului — deci nu are voie sa
 * citeasca randul din `payments` (RLS-ul e `auth.uid() = id_user`) si nici sa se
 * aboneze la el. SQL-ul trimite in schimb starea finala pe topicul ne-privat
 * `plata:<id>`, iar id-ul platii, un UUID aleator, tine loc de cheie de acces.
 *
 * Pe canal nu circula decat status si motiv. Fara id (inca nu s-a creat plata)
 * nu se deschide nimic.
 */
export function useStarePlata(idPlata: string | null): Stare {
  const [stare, setStare] = useState<Stare>(INITIALA);

  useEffect(() => {
    setStare(INITIALA);

    if (!idPlata) return;

    const supabase = createClient();
    let activ = true;

    const canal = supabase.channel(`plata:${idPlata}`).on(
      "broadcast",
      { event: "stare" },
      ({ payload }) => {
        const plata = payload as { status: StarePlata; motiv: string | null };

        if (!plata?.status) return;

        setStare({ status: plata.status, motiv: plata.motiv ?? null });
      },
    );

    // Daca raspunsul vine intre crearea platii si abonare, mesajul se pierde — pe
    // un canal de broadcast nu exista istoric. O citire imediat dupa SUBSCRIBED
    // inchide fereastra; un eveniment sosit intre timp are prioritate, ca sa nu
    // dam starea inapoi.
    const opreste = abonareAutentificata(supabase, canal, () => {
      void (async () => {
        const raspuns = await fetch(`/api/payments/${idPlata}`).catch(() => null);

        if (!activ || !raspuns?.ok) return;

        const date = (await raspuns.json().catch(() => null)) as Stare | null;

        if (!activ || !date?.status) return;

        setStare((curenta) => (curenta.status ? curenta : date));
      })();
    });

    return () => {
      activ = false;
      opreste();
    };
  }, [idPlata]);

  return stare;
}
