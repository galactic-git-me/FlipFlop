import { NextRequest, NextResponse } from "next/server";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await params;
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000";
  try {
    const response = await fetch(`${backendUrl}/api/cases/${caseId}/3d-sourcing`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json({ error: "Failed to update sourcing evidence", details: String(error) }, { status: 500 });
  }
}
