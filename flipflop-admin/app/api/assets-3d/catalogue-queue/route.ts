import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/assets-3d/catalogue-queue${request.nextUrl.search}`, {
      headers: {
        Authorization: request.headers.get("authorization") || "",
        Cookie: request.headers.get("cookie") || "",
      },
      cache: "no-store",
    });
    const text = await response.text();
    let payload: unknown;
    try { payload = JSON.parse(text); } catch { payload = { detail: text || "Could not load catalogue asset queue" }; }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Could not load catalogue asset queue" }, { status: 500 });
  }
}
