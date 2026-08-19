import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { supabaseConfigurat } from "@/lib/supabase/configurat";

/**
 * Rute pe care middleware-ul nu le redirectioneaza. Proxy-ul backend isi face
 * propria verificare si trebuie sa poata raspunde cu JSON 401, nu cu HTML de login.
 */
const RUTE_PUBLICE = [
  "/",
  "/login",
  "/register",
  "/auth",
  "/api/health",
  "/api/backend",
];

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
    process.env.SUPABASE_INTERNAL_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
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
