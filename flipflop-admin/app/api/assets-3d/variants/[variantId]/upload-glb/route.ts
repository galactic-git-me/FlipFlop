import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ variantId: string }> },
) {
  const { variantId } = await params;
  try {
    const body = await request.formData();
    const response = await fetch(
      `${BACKEND_URL}/api/assets-3d/variants/${encodeURIComponent(variantId)}/upload-glb`,
      {
        method: "POST",
        headers: {
          Authorization: request.headers.get("authorization") || "",
          Cookie: request.headers.get("cookie") || "",
        },
        body,
      },
    );
    const text = await response.text();
    let payload: unknown;
    try { payload = JSON.parse(text); } catch { payload = { detail: text || "GLB upload failed" }; }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "GLB upload failed" },
      { status: 500 },
    );
  }
}
