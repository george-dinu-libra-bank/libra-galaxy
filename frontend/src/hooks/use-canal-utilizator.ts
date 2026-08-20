"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

/**
 * Un transfer produce doua mesaje in aceeasi milisecunda (soldul si
 * tranzactia). Asteptam putin si facem un singur refresh pentru toata rafala.
 */
const FEREASTRA_REFRESH = 250;

/** Ce trimite triggerul din 0011_realtime.sql pe evenimentul 'tranzactie'. */
export type EvenimentTranzactie = {
  id: string;
  suma: number;
  valuta: string;
  descriere: string | null;
  creat_la: string;
  directie: "trimisa" | "primita" | "proprie";
  /** Numele celuilalt om, sau al grupului. Null daca nu s-a putut afla. */
  contraparte: string | null;
  /** Poza contrapartii. Null la grupuri si la profilurile fara avatar. */
  poza: string | null;
  /** Adevarat doar cand banii chiar au venit de la altcineva. */
  notifica: boolean;
};

/**
 * Asculta canalul privat „user:<id>" si cere Next-ului sa re-randeze ecranul
 * curent la orice miscare de bani. Nu tine date in client: adevarul ramane in
 * Server Components, care se recitesc la router.refresh().
 *
 * Atentie daca umbla cineva la lib/data/*: functiile de acolo apeleaza cookies()
 * prin createClient(), deci rutele sunt dinamice si refresh-ul chiar
 * reinterogheaza. Invelite in unstable_cache, realtime ar inceta tacut sa mai
 * reflecte adevarul.
 */
export function useCanalUtilizator(
  idUtilizator: string,
  laIncasare: (eveniment: EvenimentTranzactie) => void,
) {
  const router = useRouter();

  // Callback-ul se tine in ref: o functie noua la fiecare randare ar reface
  // abonamentul (deconectare + reconectare) degeaba.
  const laIncasareRef = useRef(laIncasare);
  laIncasareRef.current = laIncasare;

  useEffect(() => {
    const supabase = createClient();

    let activ = true;
    let cronometru: ReturnType<typeof setTimeout> | null = null;

    function programeazaRefresh() {
      if (cronometru) clearTimeout(cronometru);
      cronometru = setTimeout(() => {
        cronometru = null;
        if (activ) router.refresh();
      }, FEREASTRA_REFRESH);
    }

    const canal = supabase
      .channel(`user:${idUtilizator}`, { config: { private: true } })
      .on("broadcast", { event: "tranzactie" }, ({ payload }) => {
        const eveniment = payload as EvenimentTranzactie;
        if (eveniment.notifica) laIncasareRef.current(eveniment);
        programeazaRefresh();
      })
      .on("broadcast", { event: "sold" }, () => {
        programeazaRefresh();
      });

    // Canalul e privat, deci trece prin RLS pe realtime.messages: are nevoie de
    // JWT-ul sesiunii, nu doar de cheia anon. Cookie-urile sunt deja tinute la
    // zi de middleware (lib/supabase/middleware.ts).
    void (async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!activ) return;

      await supabase.realtime.setAuth(session?.access_token ?? null);

      canal.subscribe((stare, eroare) => {
        if (stare === "CHANNEL_ERROR") {
          // Aici ajunge si refuzul politicii, daca topicul nu e al tau.
          console.error("Realtime — canal indisponibil:", eroare);
        }
      });
    })();

    // Token-ul expira in aproximativ o ora. Fara reimprospatare, serverul
    // Realtime inchide canalul si utilizatorul se intoarce, tacut, la reload.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((eveniment, session) => {
      if (eveniment === "TOKEN_REFRESHED" || eveniment === "SIGNED_IN") {
        void supabase.realtime.setAuth(session?.access_token ?? null);
      }
    });

    return () => {
      activ = false;
      if (cronometru) clearTimeout(cronometru);
      subscription.unsubscribe();
      void supabase.removeChannel(canal);
    };
  }, [idUtilizator, router]);
}
