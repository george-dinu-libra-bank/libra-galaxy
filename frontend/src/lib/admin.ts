import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type UtilizatorAdmin = {
  id: string;
  email: string;
  token: string;
};

/**
 * Valoarea din `public.user_roles.role` care da drepturi de administrator.
 * Aceeasi in trei locuri care trebuie sa spuna acelasi lucru: aici, in
 * backend/app/api/dependencies.py (ROL_ADMIN) si in public.este_administrator()
 * din baza de date. Cand au fost diferite, oamenii intrau in interfata de admin
 * si primeau 403 la fiecare apel.
 */
const ROL_ADMIN = "admin";

/**
 * Utilizatorul curent, daca e administrator. Altfel null.
 *
 * Se ruleaza numai pe server. Rolul se citeste din `public.user_roles` la
* fiecare cerere, nu din token: un rol pus in JWT ar ramane valabil pana expira
 * tokenul, inclusiv dupa ce i-a fost luat cuiva dreptul.
 *
 * Interogarea merge cu sesiunea utilizatorului, deci trece prin politica
 * "Enable users to view their own data only" de pe user_roles — fiecare isi
 * vede doar propriul rand. Aceeasi verificare exista si in backend
 * (`cere_administrator`), pe fiecare ruta. Garda de aici tine ecranul ascuns;
 * bariera reala e acolo.
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

  // Filtrare pe rol + `limit(1)`, nu `maybeSingle()` si nu `single()`:
  //  - `single()` trateaza lipsa randului ca eroare, iar checkAdmin se apeleaza
  //    si din /setari pentru fiecare utilizator, deci umplea logurile cu
  //    „erori" pentru comportamentul normal;
  //  - `maybeSingle()` rezolva aia, dar arunca la DOUA randuri, iar tabela n-are
  //    index unic pe (user_id, role). S-a intamplat: un rand duplicat a dat
  //    afara din /admin un administrator adevarat. Backendul foloseste aceeasi
  //    forma in `cere_administrator`.
  const { data, error } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .eq("role", ROL_ADMIN)
    .limit(1);

  if (error) {
    console.error(`Nu am putut citi rolul pentru id=${user.id}:`, error.message);
    return null;
  }

  if (!data || data.length === 0) return null;

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
