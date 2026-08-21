import { NextResponse } from "next/server";
import { BACKEND_INTERNAL_URL as BACKEND_URL } from "@/lib/env";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/health`, { cache: "no-store" });
    if (!response.ok) throw new Error("backend unhealthy");
    return NextResponse.json({ status: "ok" });
  } catch {
    return NextResponse.json({ status: "degraded" }, { status: 503 });
  }
}
