"use client";

import type { RealtimeChannel } from "@supabase/supabase-js";
import type { createClient } from "@/lib/supabase/client";

type Client = ReturnType<typeof createClient>;

/**
 * Aboneaza un canal Realtime cu JWT-ul sesiunii si il tine autentificat cand
 * token-ul se reimprospateaza.
 *
 * Canalele pe care le folosim trec prin RLS (broadcast privat sau
 * postgres_changes pe tabele cu politici), deci au nevoie de token-ul
 * utilizatorului, nu doar de cheia anon. Token-ul expira in aproximativ o ora:
 * fara reimprospatare, serverul Realtime inchide canalul si ecranul se intoarce,
 * tacut, la reload.
 *
 * Intoarce functia de curatare — se apeleaza la demontare.
 */
export function abonareAutentificata(
  supabase: Client,
  canal: RealtimeChannel,
  laAbonare?: () => void,
) {
  let activ = true;

  void (async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!activ) return;

    await supabase.realtime.setAuth(session?.access_token ?? null);

    canal.subscribe((stare, eroare) => {
      if (stare === "SUBSCRIBED") {
        laAbonare?.();
        return;
      }

      if (stare === "CHANNEL_ERROR") {
        // Aici ajunge si refuzul politicii, daca randul nu e al tau.
        console.error("Realtime — canal indisponibil:", eroare);
      }
    });
  })();

  const {
    data: { subscription },
  } = supabase.auth.onAuthStateChange((eveniment, session) => {
    if (eveniment === "TOKEN_REFRESHED" || eveniment === "SIGNED_IN") {
      void supabase.realtime.setAuth(session?.access_token ?? null);
    }
  });

  return () => {
    activ = false;
    subscription.unsubscribe();
    void supabase.removeChannel(canal);
  };
}
