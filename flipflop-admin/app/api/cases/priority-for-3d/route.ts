import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") || "30";

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
