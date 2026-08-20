import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type UtilizatorAdmin = {
  id: string;
  email: string;
  token: string;
};

/**
 * Utilizatorul curent, daca e administrator. Altfel null.
 *
 * Se ruleaza numai pe server. Rolul se citeste din `user_roles` la fiecare
 * cerere, nu din token: un rol pus in JWT ar ramane valabil pana expira
 * tokenul, inclusiv dupa ce i-a fost luat cuiva dreptul.
 *
 * Interogarea merge cu sesiunea utilizatorului, deci politica din 0005 e cea
 * care decide ce vede — iar aceeasi verificare exista si in backend, pe fiecare
 * ruta. Garda de aici tine ecranul ascuns; bariera reala e acolo.
 */
export async function checkAdmin(): Promise<UtilizatorAdmin | null> {
  const supabase = await createClient();

  const [
    {
      data: { user },
    },
    {
      data: { session },
    },
  ] = await Promise.all([supabase.auth.getUser(), supabase.auth.getSession()]);

  if (!user || !session?.access_token) return null;

  const { data, error } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .eq("role", "admin")
    .maybeSingle();

  if (error || !data) return null;

  return { id: user.id, email: user.email ?? "", token: session.access_token };
}

/**
 * Ca `checkAdmin`, dar opreste randarea daca nu e cazul.
 *
 * Cine nu e autentificat ajunge la login; cine e autentificat dar nu e
 * administrator ajunge la dashboard, nu la o pagina de eroare: nu are ce sti
 * despre existenta acestei zone.
 */
export async function cereAdmin(): Promise<UtilizatorAdmin> {
  const admin = await checkAdmin();
  if (!admin) redirect("/dashboard");
  return admin;
}
