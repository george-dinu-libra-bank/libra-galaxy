import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

/**
 * Client Supabase pentru Server Components, Route Handlers si Server Actions.
 * In Next 16 `cookies()` este asincron, deci functia se asteapta cu `await`.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // Apelat dintr-un Server Component: cookie-urile sunt reimprospatate
            // de middleware, deci putem ignora eroarea.
          }
        },
      },
    },
  );
}
