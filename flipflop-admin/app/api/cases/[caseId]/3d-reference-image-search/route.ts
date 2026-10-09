import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.FLIPFLOP_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await params;
  const backendUrl = new URL(
    `${API_URL}/api/cases/${encodeURIComponent(caseId)}/3d-reference-image-search`,
  );
  const query = request.nextUrl.searchParams.get("query");
  if (query !== null) backendUrl.searchParams.set("query", query);

  const response = await fetch(backendUrl, { cache: "no-store" });
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
