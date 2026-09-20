import { NextRequest, NextResponse } from "next/server";
import { createBuildPerformancePortal } from "@/lib/performance-portal";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File;
    const buildId = String(formData.get("build_id") || "").trim();

    if (!file) {
      return NextResponse.json(
        { success: false, error: "No file provided" },
        { status: 400 }
      );
    }
    if (!/^\d+$/.test(buildId)) {
      return NextResponse.json(
        { success: false, error: "A valid build_id is required" },
        { status: 400 }
      );
    }

    const jsonText = await file.text();
    const performanceData = JSON.parse(jsonText);

    const { portalPath } = await createBuildPerformancePortal(buildId, performanceData);

    return NextResponse.json(
      { success: true, message: "Performance data saved and build portal generated", portalPath },
      { status: 200 }
    );
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Unknown error";
    console.error("Error uploading performance card data:", msg);
    return NextResponse.json(
      { success: false, error: msg },
      { status: 500 }
    );
  }
}
