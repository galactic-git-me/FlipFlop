import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.BACKEND_URL || process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";
async function relayJson(response: Response) {
  const body = await response.text();
  try {
    return NextResponse.json(JSON.parse(body), { status: response.status });
  } catch {
    const detail = body.trim().replace(/\s+/g, " ").slice(0, 240);
    return NextResponse.json({ detail: detail || `Image service returned an empty response (${response.status}).` }, { status: response.status });
  }
}
export async function GET(request: NextRequest, context: { params: Promise<{ variantId: string }> }) {
  const { variantId } = await context.params;
  if (!/^\d+$/.test(variantId)) return NextResponse.json({ detail: "Invalid component" }, { status: 400 });
  try {
    const suffix = `?query=${encodeURIComponent(request.nextUrl.searchParams.get("query") || "")}`;
    const response = await fetch(`${API_URL}/api/assets-3d/catalogue/components/${variantId}/image-search${suffix}`, {
      method: "GET", cache: "no-store",
      headers: { "content-type": "application/json", cookie: request.headers.get("cookie") || "", authorization: request.headers.get("authorization") || "" },
      
    });
    return await relayJson(response);
  } catch (error) {
    const detail = error instanceof Error && error.name === "TimeoutError" ? "The image service timed out. Please retry." : "The image request could not finish. Please retry.";
    return NextResponse.json({ detail }, { status: 502 });
  }
}
