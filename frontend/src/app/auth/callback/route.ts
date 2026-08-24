import { NextResponse, type NextRequest } from "next/server";
import { inregistreazaDispozitiv } from "@/lib/data/dispozitive";
import { createClient } from "@/lib/supabase/server";

/**
 * Tinta linkurilor din emailurile Supabase (confirmare cont, resetare parola).
 * Schimba codul primit pe o sesiune si duce utilizatorul mai departe.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";

  const destinatie = next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // Si asta e un login: aici ajunge cine si-a resetat parola sau si-a
      // confirmat contul din email.
      await inregistreazaDispozitiv();
      return NextResponse.redirect(`${origin}${destinatie}`);
    }
  }

  return NextResponse.redirect(
    `${origin}/login?eroare=${encodeURIComponent("Linkul a expirat sau a fost deja folosit.")}`,
  );
}
