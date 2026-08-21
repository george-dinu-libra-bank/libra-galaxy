import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { SUPABASE_ANON_KEY, SUPABASE_INTERNAL_URL, supabaseConfigurat } from "@/lib/env";

/**
 * Rute pe care middleware-ul nu le redirectioneaza catre /login.
 *
 * „/api" nu inseamna „fara autentificare": rutele de acolo raspund in JSON, deci
 * isi verifica singure sesiunea si intorc 401, nu un redirect 307 catre o pagina
 * de login pe care un fetch() n-are ce sa faca. /shop e vitrina publica (Galaxy
 * Shop), navigabila fara cont.
 */
const RUTE_PUBLICE = ["/", "/login", "/register", "/auth", "/shop", "/api"];

function estePublica(pathname: string) {
  return RUTE_PUBLICE.some(
    (ruta) => pathname === ruta || pathname.startsWith(`${ruta}/`),
  );
}

/**
 * Reimprospateaza sesiunea la fiecare request si redirectioneaza:
 *  - utilizator fara sesiune pe ruta protejata -> /login?redirectTo=...
 *  - utilizator logat pe /login sau /register   -> /dashboard
 */
export async function updateSession(request: NextRequest) {
  // Fara credentiale Supabase, lasam totul accesibil (mod previzualizare UI).
  if (!supabaseConfigurat) return NextResponse.next({ request });

  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    SUPABASE_INTERNAL_URL,
    SUPABASE_ANON_KEY,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => {
            request.cookies.set(name, value);
          });

          response = NextResponse.next({ request });

          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    },
  );

  // IMPORTANT: nu se insereaza cod intre createServerClient si getUser().
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, search } = request.nextUrl;

  if (!user && !estePublica(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?redirectTo=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  if (user && (pathname === "/login" || pathname === "/register")) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return response;
}
