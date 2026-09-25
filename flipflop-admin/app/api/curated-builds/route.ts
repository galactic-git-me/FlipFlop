import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

async function proxy(request: NextRequest, method: "GET" | "POST" | "PATCH") {
  const suffix = request.nextUrl.search || "";
  try {
    const response = await fetch(`${BACKEND_URL}/api/curated-builds${suffix}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("authorization") || "",
        Cookie: request.headers.get("cookie") || "",
      },
      ...(method === "GET" ? {} : { body: await request.text() }),
    });
    const data = await response.text();
    return new NextResponse(data, { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Backend unavailable" }, { status: 502 });
  }
}

export const GET = (request: NextRequest) => proxy(request, "GET");
export const POST = (request: NextRequest) => proxy(request, "POST");
