import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/custom-builds${request.nextUrl.search}`, {
      headers: { Authorization: request.headers.get("authorization") || "", Cookie: request.headers.get("cookie") || "" },
      cache: "no-store",
    });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Backend unavailable" }, { status: 502 });
  }
}
