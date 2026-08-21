import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function GET() {
  try {
    // Fetch from backend assets API
    const response = await fetch(`${BACKEND_URL}/api/assets-3d/public`, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      console.error("Backend error:", response.status, response.statusText);
      return NextResponse.json({ error: "Failed to fetch assets" }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching assets:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
