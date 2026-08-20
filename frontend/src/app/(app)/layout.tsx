import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { BottomNav } from "@/components/shell/bottom-nav";
import { createClient } from "@/lib/supabase/server";

/**
 * Cadrul comun al ecranelor autentificate (dashboard, istoric, transfer,
 * carduri, beneficiari, setari): verifica sesiunea o singura data si
 * monteaza navigarea de jos. Fiecare pagina isi aduce doar continutul.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="min-h-dvh pb-24">
      {children}
      <BottomNav />
    </div>
  );
}
