import { NextResponse } from "next/server";
import { stareaPlatii } from "@/lib/services/plati";

/**
 * GET /api/payments/<id> — starea unei plati, pentru ecranul de checkout.
 *
 * Rezultatul vine in mod normal prin Realtime, pe topicul `plata:<id>`. Ruta
 * asta acopera doar cazul in care raspunsul a sosit inainte ca magazinul sa
 * apuce sa se aboneze — o singura citire, imediat dupa SUBSCRIBED.
 *
 * Nu cere sesiune, ca si POST /api/payments: cine cumpara nu e neaparat
 * posesorul cardului. Cheia de acces e id-ul platii, un UUID pe care il stie
 * doar cine a deschis-o; de aceea raspunsul nu contine decat status si motiv.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const stare = await stareaPlatii(id);

  if (!stare) return NextResponse.json({ eroare: "Plata nu există." }, { status: 404 });

  return NextResponse.json(stare);
}
