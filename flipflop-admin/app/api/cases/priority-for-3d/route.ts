import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  // The campaign starts with 30 frozen cases, but curated exceptions may have
  // a later rank and must remain visible in the review UI.
  const limit = searchParams.get("limit") || "100";

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000";
  const apiUrl = `${backendUrl}/api/cases/priority-for-3d?limit=${limit}`;

  try {
    const response = await fetch(apiUrl);
    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Cases API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch cases", details: String(error) },
      { status: 500 }
    );
  }
}

export async function POST() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000";
  try {
    const response = await fetch(`${backendUrl}/api/cases/priority-for-3d/freeze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json({ error: "Failed to freeze priority campaign", details: String(error) }, { status: 500 });
  }
}
