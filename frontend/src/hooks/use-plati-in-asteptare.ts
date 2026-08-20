"use client";

import { useCallback, useEffect, useState } from "react";
import { laPlataInAsteptare, type PlataInAsteptare, type RandPlata } from "@/lib/plati";
import { createClient } from "@/lib/supabase/client";
import { abonareAutentificata } from "@/lib/supabase/realtime";

/**
 * Coada de plati proprii care asteapta un raspuns.
 *
 * Filtrul e pe id_user, deci nu vin niciodata platile altcuiva. O plata noua
 * (INSERT) intra in coada; orice UPDATE care o scoate din PENDING_APPROVAL o
 * elimina — inclusiv cand raspunsul a venit din alta fila.
 *
 * `initiale` vine din Server Component, ca un refresh sa nu piarda o plata
 * deschisa inainte ca ecranul sa fie montat.
 */
export function usePlatiInAsteptare(idUtilizator: string, initiale: PlataInAsteptare[]) {
  const [plati, setPlati] = useState<PlataInAsteptare[]>(initiale);

  const elimina = useCallback((id: string) => {
    setPlati((lista) => lista.filter((plata) => plata.id !== id));
  }, []);

  useEffect(() => {
    const supabase = createClient();

    const canal = supabase
      .channel(`plati:${idUtilizator}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "payments",
          filter: `id_user=eq.${idUtilizator}`,
        },
        ({ new: rand }) => {
          const plata = rand as RandPlata;

          if (plata.status !== "PENDING_APPROVAL") return;

          setPlati((lista) =>
            // Acelasi rand poate sosi de doua ori dupa o reconectare.
            lista.some((p) => p.id === plata.id)
              ? lista
              : [...lista, laPlataInAsteptare(plata)],
          );
        },
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "payments",
          filter: `id_user=eq.${idUtilizator}`,
        },
        ({ new: rand }) => {
          const plata = rand as RandPlata;

          if (plata.status === "PENDING_APPROVAL") return;

          setPlati((lista) => lista.filter((p) => p.id !== plata.id));
        },
      );

    return abonareAutentificata(supabase, canal);
  }, [idUtilizator]);

  return { plati, elimina };
}
