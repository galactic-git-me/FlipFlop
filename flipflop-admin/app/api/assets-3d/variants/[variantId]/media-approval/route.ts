import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";

export async function PUT(request: NextRequest, context: { params: Promise<{ variantId: string }> }) {
  try {
    const { variantId } = await context.params;
    const response = await fetch(`${API_URL}/api/assets-3d/variants/${encodeURIComponent(variantId)}/media-approval`, {
      method: "PUT", headers: { "content-type": "application/json", cookie: request.headers.get("cookie") || "" },
      body: await request.text(), cache: "no-store",
    });
    const body = await response.text();
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return new NextResponse(body, { status: response.status, headers: { "content-type": contentType } });
    }
    return NextResponse.json({ detail: body.trim() || `Media approval API returned HTTP ${response.status} ${response.statusText}` }, { status: response.status });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Could not save photo approval" }, { status: 502 });
  }
}
