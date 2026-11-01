import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.BACKEND_URL || process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";
export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${API_URL}/api/assets-3d/catalogue/photo-queue`, {
      cache: "no-store", headers: { cookie: request.headers.get("cookie") || "", authorization: request.headers.get("authorization") || "" },
    });
    const payload = await response.json().catch(() => ({ detail: `Photo inventory returned HTTP ${response.status}` }));
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Could not load catalogue photos. Try refreshing." }, { status: 502 });
  }
}
