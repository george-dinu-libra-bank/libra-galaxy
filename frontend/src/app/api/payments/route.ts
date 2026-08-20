import { NextResponse } from "next/server";
import { creeazaPlata } from "@/lib/services/plati";

/**
 * POST /api/payments — magazinul cere o plata cu datele unui card Libra.
 *
 * Ruta ramane subtire: autentificarea, validarea cardului si suma din catalog
 * sunt treaba serviciului (lib/services/plati.ts), iar regulile bancare stau in
 * SQL. Raspunsul e cel asteptat de checkout: { paymentId, status }.
 */
export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as {
    slug?: unknown;
    numarCard?: unknown;
    dataExpirare?: unknown;
    cvv?: unknown;
  } | null;

  if (
    typeof body?.slug !== "string" ||
    typeof body.numarCard !== "string" ||
    typeof body.dataExpirare !== "string" ||
    typeof body.cvv !== "string"
  ) {
    return NextResponse.json({ eroare: "Cerere invalidă." }, { status: 400 });
  }

  const rezultat = await creeazaPlata({
    slug: body.slug,
    numarCard: body.numarCard,
    dataExpirare: body.dataExpirare,
    cvv: body.cvv,
  });

  if (!rezultat.ok) {
    return NextResponse.json({ eroare: rezultat.eroare }, { status: rezultat.http });
  }

  return NextResponse.json({
    paymentId: rezultat.plata.id,
    status: rezultat.plata.status,
    expiraLa: rezultat.plata.expiraLa,
  });
}
