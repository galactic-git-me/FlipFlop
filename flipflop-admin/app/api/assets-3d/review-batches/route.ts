import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const response = await fetch(`${BACKEND_URL}/api/assets-3d/review-batches`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("authorization") || "",
        Cookie: request.headers.get("cookie") || "",
      },
      body,
      cache: "no-store",
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json({ detail: `Could not create the 3D review batch: ${error instanceof Error ? error.message : String(error)}` }, { status: 502 });
  }
}
