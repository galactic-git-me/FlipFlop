import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const category = request.nextUrl.searchParams.get("category") || "case";
  const backend = process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000";
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
