import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:18000";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/assets-3d`, {
      headers: {
        "Authorization": request.headers.get("authorization") || "",
      },
    });

    if (!response.ok) {
      return NextResponse.json({ error: "Failed to fetch assets" }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching assets:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
