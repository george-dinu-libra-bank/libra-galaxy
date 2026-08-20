import { createBrowserClient } from "@supabase/ssr";

function creeazaClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

// Tipul se ia de la fabrica de mai sus, nu direct de la createBrowserClient:
// aceea are doua supraincarcari, iar ReturnType<typeof ...> o alege pe ultima
// si scapa tot clientul in `any` (dispar tipurile pe .channel si .auth).
let clientMemorat: ReturnType<typeof creeazaClient> | null = null;

/**
 * Client Supabase pentru componente client. Un singur exemplar pe fila: altfel
 * fiecare montare ar deschide inca o conexiune WebSocket catre Realtime.
 */
export function createClient() {
  clientMemorat ??= creeazaClient();
  return clientMemorat;
}
