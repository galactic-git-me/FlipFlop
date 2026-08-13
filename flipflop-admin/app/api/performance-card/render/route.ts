import { NextRequest, NextResponse } from "next/server";
import * as fs from "fs/promises";
import * as path from "path";
import JSZip from "jszip";

/**
 * Splits the card into 3 roughly-equal vertical bands, but only ever cuts
 * at a real ".section" boundary (or the very top/bottom) — never through
 * the middle of a benchmark grid, game card row, etc.
 */
function computeSplitBoundaries(totalHeight: number, sectionTops: number[]): number[] {
  const candidates = [0, ...sectionTops, totalHeight].sort((a, b) => a - b);
  const target = totalHeight / 3;

  const cuts: number[] = [0];
  let nextTarget = target;
  for (const y of candidates) {
    if (y <= cuts[cuts.length - 1]) continue;
    if (y >= nextTarget && cuts.length < 3) {
      cuts.push(y);
      nextTarget += target;
    }
  }
  cuts.push(totalHeight);

  // Fewer than 4 real boundaries available (e.g. very short card) — just
  // fall back to even thirds rather than producing empty/duplicate bands.
  if (cuts.length !== 4 || new Set(cuts).size !== 4) {
    return [0, target, target * 2, totalHeight];
  }
  return cuts;
}

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
    let performanceData;
    try {
      performanceData = JSON.parse(jsonText);
    } catch (e) {
      return NextResponse.json(
        { success: false, error: "Invalid JSON file" },
        { status: 400 }
      );
    }

    const targetDir = path.join(
      process.cwd(),
      "..",
      "..",
      "Personalised Website"
    );

    await fs.mkdir(targetDir, { recursive: true });
    const targetFile = path.join(targetDir, "performance-data.json");

    await fs.writeFile(
      targetFile,
      JSON.stringify(performanceData, null, 2),
      "utf-8"
    );

    console.log(`[Performance Card] Saved JSON to ${targetFile}`);

    try {
      const { chromium } = await import("playwright");
      console.log("[Performance Card] Launching Playwright browser...");

      const browser = await chromium.launch({
        headless: true,
        args: ["--no-sandbox", "--disable-setuid-sandbox"]
      });

      const page = await browser.newPage();
      console.log("[Performance Card] Navigating to localhost:5173...");

      await page.goto("http://localhost:5173", {
        waitUntil: "networkidle",
        timeout: 20000,
      });

      console.log("[Performance Card] Waiting for initial animation to complete...");
      await page.waitForTimeout(4000);

      // page.screenshot({ clip }) can only capture what's within the current
      // viewport — the default (~720px tall) is far shorter than this card,
      // so any clip below the fold errors as "outside the resulting image".
      // Resize the viewport to the full document height before measuring or
      // screenshotting anything.
      const fullHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      await page.setViewportSize({ width: 1280, height: Math.ceil(fullHeight) + 50 });

      const card = page.locator("#ffCard");
      const cardBox = await card.boundingBox();
      if (!cardBox) {
        throw new Error("Could not measure #ffCard — did render.js populate it?");
      }

      const sectionTops = await page.$$eval(".section", (els) =>
        els.map((el) => el.getBoundingClientRect().top + window.scrollY)
      );

      const boundaries = computeSplitBoundaries(cardBox.y + cardBox.height, sectionTops);
      console.log("[Performance Card] Split boundaries:", boundaries);

      const zip = new JSZip();
      for (let i = 0; i < 3; i++) {
        const y = boundaries[i];
        const height = boundaries[i + 1] - y;
        const screenshot = await page.screenshot({
          type: "png",
          clip: { x: cardBox.x, y, width: cardBox.width, height },
          timeout: 10000,
        });
        zip.file(`performance-card-part-${i + 1}.png`, screenshot);
      }

      await browser.close();

      const zipBuffer = await zip.generateAsync({ type: "nodebuffer" });
      console.log(`[Performance Card] Zip built: ${zipBuffer.length} bytes`);

      return new NextResponse(new Blob([new Uint8Array(zipBuffer)]), {
        status: 200,
        headers: {
          "Content-Type": "application/zip",
          "Content-Disposition": "attachment; filename=performance-card-sections.zip",
          "Cache-Control": "no-cache, no-store, must-revalidate",
        },
      });
    } catch (playwrightError) {
      const msg = playwrightError instanceof Error ? playwrightError.message : "Playwright error";
      console.error("[Performance Card] Playwright error:", msg);
      console.error("[Performance Card] Stack:", playwrightError instanceof Error ? playwrightError.stack : "");

      return NextResponse.json(
        {
          success: true,
          message: "JSON saved but could not render preview. Ensure localhost:5173 is running.",
          error: msg
        },
        { status: 200 }
      );
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Unknown error";
    console.error("[Performance Card] Fatal error:", msg);
    return NextResponse.json(
      { success: false, error: msg },
      { status: 500 }
    );
  }
}
