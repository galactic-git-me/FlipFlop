import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const NASA_KEY = process.env.NASA_API_KEY ?? "DEMO_KEY";
const APOD_API = `https://api.nasa.gov/planetary/apod?api_key=${NASA_KEY}&count=1`;

// Pick a random APOD and proxy the image back so Three.js can load it same-origin
export async function GET(request: Request) {
  try {
    const meta = await fetch(APOD_API, { next: { revalidate: 0 } });
    if (!meta.ok) throw new Error("APOD API failed");

    const [entry] = await meta.json();

    // Some APODs are YouTube videos — skip those and fall back to local image
    if (entry.media_type !== "image") {
      return NextResponse.redirect(new URL("/space-bg.jpg", request.url));
    }

    const imgUrl = entry.hdurl ?? entry.url;
    const img = await fetch(imgUrl);
    if (!img.ok) throw new Error("Image fetch failed");

    const buffer = await img.arrayBuffer();
    const contentType = img.headers.get("content-type") ?? "image/jpeg";

    return new NextResponse(buffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch {
    // Fall back to bundled space image
    const buffer = await readFile(join(process.cwd(), "public", "space-bg.jpg"));
    return new NextResponse(buffer, {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=3600" },
    });
  }
}
