import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4311";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/assets-3d${new URL(request.url).search}`, {
      headers: {
        "Content-Type": "application/json",
        "Authorization": request.headers.get("authorization") || "",
        "Cookie": request.headers.get("cookie") || "",
      },
    });

    console.log("Backend response status:", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Backend error:", response.status, response.statusText, errorText.substring(0, 100));
      return NextResponse.json({ error: "Failed to fetch assets", status: response.status }, { status: response.status });
    }

    const data = await response.json();
    console.log("Successfully parsed JSON, items:", Array.isArray(data) ? data.length : "not array");
    return NextResponse.json(data);
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error("Error fetching assets:", errorMsg);
    return NextResponse.json({ error: "Internal server error", detail: errorMsg }, { status: 500 });
  }
}
