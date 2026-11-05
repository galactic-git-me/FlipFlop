import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.FLIPFLOP_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4311";

export async function POST(request: NextRequest, context: { params: Promise<{ caseId: string }> }) {
  try {
    const { caseId } = await context.params;
    const response = await fetch(`${API_URL}/api/assets-3d/cases/${caseId}/generate`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        cookie: request.headers.get("cookie") || "",
      },
      body: await request.text(),
      cache: "no-store",
    });

    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json({ detail: `Could not reach the 3D generation service: ${error instanceof Error ? error.message : String(error)}` }, { status: 502 });
  }
}
