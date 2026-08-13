import { NextRequest, NextResponse } from "next/server";
import * as fs from "fs/promises";
import * as path from "path";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json(
        { success: false, error: "No file provided" },
        { status: 400 }
      );
    }

    const jsonText = await file.text();
    const performanceData = JSON.parse(jsonText);

    const targetDir = path.join(
      process.cwd(),
      "..",
      "..",
      "Personalised Website"
    );
    const targetFile = path.join(targetDir, "performance-data.json");

    await fs.writeFile(
      targetFile,
      JSON.stringify(performanceData, null, 2),
      "utf-8"
    );

    return NextResponse.json(
      { success: true, message: "Performance card data saved" },
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
