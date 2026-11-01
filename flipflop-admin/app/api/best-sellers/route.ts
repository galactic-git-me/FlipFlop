import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const category = request.nextUrl.searchParams.get("category") || "case";
  // This Route Handler runs server-side. NEXT_PUBLIC_API_URL is `/api` in
  // production and is intended for browser calls, not backend-to-backend
  // requests. Gem Radar has its own production service and is mounted on the
  // main API during local development.
  const backend = (process.env.GEMRADAR_URL ?? process.env.BACKEND_URL ?? "http://localhost:4311").replace(/\/+$/, "");
  try {
    const response = await fetch(`${backend}/api/gem-radar/best-sellers?category=${encodeURIComponent(category)}`, { cache: "no-store" });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "Could not reach the bestseller service" }, { status: 502 });
  }
}
