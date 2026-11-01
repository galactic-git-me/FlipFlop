import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.BACKEND_URL || process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";
export async function POST(request: NextRequest, context: { params: Promise<{ variantId: string }> }) {
  const { variantId } = await context.params;
  if (!/^\d+$/.test(variantId)) return NextResponse.json({ detail: "Invalid component" }, { status: 400 });
  try {
    const response = await fetch(`${API_URL}/api/assets-3d/catalogue/components/${variantId}/hardware-photo`, {
      method: "POST", cache: "no-store", headers: { cookie: request.headers.get("cookie") || "", authorization: request.headers.get("authorization") || "" },
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch { return NextResponse.json({ detail: "Hardware photo review did not finish. Refresh to retry." }, { status: 502 }); }
}
