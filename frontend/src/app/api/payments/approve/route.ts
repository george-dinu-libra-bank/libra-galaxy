import { NextResponse } from "next/server";
import { aprobaPlata } from "@/lib/services/plati";

/**
 * POST /api/payments/approve — utilizatorul confirma plata din aplicatie.
 *
 * Clientul nu are drept de scriere pe public.payments: singurul drum catre
 * APPROVED trece pe aici, iar de aici prin public.aproba_plata, care verifica
 * din nou proprietarul, starea, expirarea, cardul si fondurile.
 */
export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { paymentId?: unknown } | null;

  if (typeof body?.paymentId !== "string") {
    return NextResponse.json({ eroare: "Cerere invalidă." }, { status: 400 });
  }

  const rezultat = await aprobaPlata(body.paymentId);

  if (!rezultat.ok) {
    return NextResponse.json({ eroare: rezultat.eroare }, { status: rezultat.http });
  }

  return NextResponse.json({
    paymentId: rezultat.plata.id,
    status: rezultat.plata.status,
    motiv: rezultat.plata.motiv,
  });
}
