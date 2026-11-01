import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.BACKEND_URL || process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";
export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${API_URL}/api/assets-3d/catalogue/approve-main-photos`, {
      method: "POST", cache: "no-store",
      headers: { "content-type": "application/json", cookie: request.headers.get("cookie") || "", authorization: request.headers.get("authorization") || "" },
      body: await request.text(),
    });
    const payload = await response.json().catch(() => ({ detail: `Photo approval returned HTTP ${response.status}` }));
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Could not save photo approvals. Refresh to check saved approvals before retrying." }, { status: 502 });
  }
}
