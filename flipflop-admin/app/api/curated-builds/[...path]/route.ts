import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }, method: "GET" | "POST" | "PATCH" | "PUT") {
  const { path } = await context.params;
  const suffix = request.nextUrl.search || "";
  try {
    const response = await fetch(`${BACKEND_URL}/api/curated-builds/${path.map(encodeURIComponent).join("/")}${suffix}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("authorization") || "",
        Cookie: request.headers.get("cookie") || "",
      },
      body: method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Backend unavailable" }, { status: 502 });
  }
}

export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => proxy(request, context, "POST");
export const PATCH = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => proxy(request, context, "PATCH");
export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => proxy(request, context, "GET");
export const PUT = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => proxy(request, context, "PUT");
