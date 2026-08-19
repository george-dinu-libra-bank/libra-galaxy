import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/health`, { cache: "no-store" });
    if (!response.ok) throw new Error("backend unhealthy");
    return NextResponse.json({ status: "ok" });
  } catch {
    return NextResponse.json({ status: "degraded" }, { status: 503 });
  }
}
