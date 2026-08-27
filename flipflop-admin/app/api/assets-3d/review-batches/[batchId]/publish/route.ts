import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:18000";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ batchId: string }> },
) {
  const { batchId } = await params;
  const response = await fetch(`${BACKEND_URL}/api/assets-3d/review-batches/${batchId}/publish`, {
    method: "POST",
    headers: {
      Authorization: request.headers.get("authorization") || "",
      Cookie: request.headers.get("cookie") || "",
    },
    cache: "no-store",
  });
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
  });
}
