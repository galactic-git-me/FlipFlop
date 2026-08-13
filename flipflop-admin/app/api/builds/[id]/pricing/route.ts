import { NextResponse } from "next/server";

// Proxies to flipflop-api's PricingBreakdown endpoint (app/api/builds_pricing.py,
// mounted directly on the FastAPI app -- not under /api/gem-radar). A relative
// fetch("/api/builds/[id]/pricing") from a client component would otherwise hit
// this Next.js app's own /api routes rather than the backend, which is exactly
// why this route needs to exist at all.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { searchParams } = new URL(req.url);
  const fetchSold = searchParams.get("fetch_sold") ?? "false";

  try {
    const backendOrigin = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4311").replace(/\/$/, "");
    const apiUrl = `${backendOrigin}/api/builds/${id}/pricing?fetch_sold=${fetchSold}`;
    const res = await fetch(apiUrl, {
      signal: AbortSignal.timeout(30000), // sold-comps fetch can hit ScrapingBee live, slower than a typical read
    });

    if (!res.ok) {
      const errorData = await res.text();
      console.error(`API error fetching ${apiUrl}:`, res.status, errorData);
      return NextResponse.json(
        { error: "Failed to fetch pricing data", detail: errorData, status: res.status },
        { status: res.status }
      );
    }

    const pricing = await res.json();
    return NextResponse.json(pricing);
  } catch (error) {
    console.error("Pricing breakdown proxy error:", error);
    return NextResponse.json(
      { error: "Failed to fetch pricing data" },
      { status: 500 }
    );
  }
}
