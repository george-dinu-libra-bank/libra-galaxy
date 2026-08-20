import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const METODE_CU_BODY = new Set(["POST", "PUT", "PATCH", "DELETE"]);

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const supabase = await createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (userError || !user || !session?.access_token) {
    return NextResponse.json({ detail: "Sesiunea este invalida sau a expirat." }, { status: 401 });
  }

  const { path } = await context.params;
  const target = new URL(path.join("/"), `${BACKEND_URL}/`);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${session.access_token}`);
  headers.set("Accept", request.headers.get("accept") ?? "application/json");
  headers.set("X-Request-ID", request.headers.get("x-request-id") ?? crypto.randomUUID());

  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const idempotencyKey = request.headers.get("idempotency-key");
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: METODE_CU_BODY.has(request.method) ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });

    const responseHeaders = new Headers();
    responseHeaders.set(
      "Content-Type",
      upstream.headers.get("content-type") ?? "application/json",
    );
    const requestId = upstream.headers.get("x-request-id");
    if (requestId) responseHeaders.set("X-Request-ID", requestId);

    // Fara asta, un PDF sau un CSV s-ar deschide in tab in loc sa se descarce,
    // si si-ar pierde numele pus de backend.
    const dispozitie = upstream.headers.get("content-disposition");
    if (dispozitie) responseHeaders.set("Content-Disposition", dispozitie);

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend-ul nu este disponibil momentan." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
