import { NextResponse } from "next/server";
import { respingePlata } from "@/lib/services/plati";

/**
 * POST /api/payments/decline — utilizatorul respinge plata din aplicatie.
 *
 * Aceleasi garantii ca la aprobare: autentificare, proprietate si un update
 * conditionat de PENDING_APPROVAL, in public.respinge_plata.
 */
export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { paymentId?: unknown } | null;

  if (typeof body?.paymentId !== "string") {
    return NextResponse.json({ eroare: "Cerere invalidă." }, { status: 400 });
  }

  const rezultat = await respingePlata(body.paymentId);

  if (!rezultat.ok) {
    return NextResponse.json({ eroare: rezultat.eroare }, { status: rezultat.http });
  }

  return NextResponse.json({
    paymentId: rezultat.plata.id,
    status: rezultat.plata.status,
  });
}
