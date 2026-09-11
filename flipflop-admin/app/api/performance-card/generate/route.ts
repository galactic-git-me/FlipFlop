import { NextRequest, NextResponse } from "next/server";
import * as fs from "fs/promises";
import * as path from "path";

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

    const buildsRoot = path.resolve(process.cwd(), "..", "builds");
    const numericBuildDir = path.join(buildsRoot, buildId);
    const paddedBuildDir = path.join(buildsRoot, buildId.padStart(3, "0"));
    let buildDir = numericBuildDir;
    try {
      await fs.stat(numericBuildDir);
    } catch {
      try {
        await fs.stat(paddedBuildDir);
        buildDir = paddedBuildDir;
      } catch {
        // New builds use their numeric ID until a padded directory is created.
      }
    }
    const targetDir = path.join(buildDir, "Performance");
    const targetFile = path.join(targetDir, "performance-data.json");

    await fs.mkdir(targetDir, { recursive: true });
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
