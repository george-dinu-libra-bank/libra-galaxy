import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { ConfirmaPlataDrawer } from "@/components/plati/confirma-plata-drawer";
import { AscultatorRealtime } from "@/components/realtime/ascultator-realtime";
import { BottomNav } from "@/components/shell/bottom-nav";
import { Notificari } from "@/components/ui/notificari";
import { obtinePlatiInAsteptare } from "@/lib/data/plati";
import { supabaseConfigurat } from "@/lib/supabase/configurat";
import { createClient } from "@/lib/supabase/server";

/**
 * Cadrul comun al ecranelor autentificate (dashboard, istoric, transfer,
 * carduri, beneficiari, setari): verifica sesiunea o singura data, monteaza
 * navigarea de jos si ascultatorul de realtime. Fiecare pagina isi aduce doar
 * continutul.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  // Cererile de plata deschise se aduc aici, nu doar pe dashboard: intrebarea
  // trebuie sa apara oriunde ar fi utilizatorul cand comerciantul o trimite.
  const platiInAsteptare = supabaseConfigurat ? await obtinePlatiInAsteptare() : [];

  return (
    <div className="min-h-dvh pb-24">
      {children}
      <BottomNav />
      {/* Sesiunea e deja rezolvata mai sus, deci id-ul se paseaza ca prop:
          clientul nu mai face un getUser() in plus. In modul previzualizare
          (fara credentiale Supabase) nu montam nimic. */}
      {supabaseConfigurat ? (
        <>
          <AscultatorRealtime idUtilizator={user.id} />
          <ConfirmaPlataDrawer idUtilizator={user.id} initiale={platiInAsteptare} />
        </>
      ) : null}
      <Notificari />
    </div>
  );
}
