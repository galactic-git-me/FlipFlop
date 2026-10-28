import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.BACKEND_URL || process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";
export async function DELETE(request: NextRequest, context: { params: Promise<{ variantId: string }> }) {
  const { variantId } = await context.params;
  if (!/^\d+$/.test(variantId)) return NextResponse.json({ detail: "Invalid component" }, { status: 400 });
  try {
    const response = await fetch(`${API_URL}/api/assets-3d/catalogue/components/${variantId}`, {
      method: "DELETE", cache: "no-store", headers: { cookie: request.headers.get("cookie") || "", authorization: request.headers.get("authorization") || "" },
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch { return NextResponse.json({ detail: "Deletion could not be confirmed. Refresh before retrying." }, { status: 502 }); }
}
