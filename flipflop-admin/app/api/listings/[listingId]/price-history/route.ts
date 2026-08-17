import { NextResponse } from "next/server";

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

export async function GET(
  request: Request,
  context: { params: Promise<{ listingId: string }> }
) {
  const { listingId } = await context.params;

  if (!listingId) {
    return NextResponse.json(
      { error: "Listing ID is required" },
      { status: 400 }
    );
  }

  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Fetch both listing and CPK price histories in parallel
    const [listingRes, cpkRes] = await Promise.all([
      fetch(
        `${backendUrl}/api/gem_radar/listings/${encodeURIComponent(listingId)}/price-history`,
        {
          headers: { "Content-Type": "application/json" },
        }
      ),
      fetch(
        `${backendUrl}/api/gem_radar/listings/${encodeURIComponent(listingId)}/cpk-price-history`,
        {
          headers: { "Content-Type": "application/json" },
        }
      ),
    ]);

    const listingData = listingRes.ok ? await listingRes.json() : { prices: [] };
    const cpkData = cpkRes.ok ? await cpkRes.json() : { prices: [] };

    return NextResponse.json({
      listingPrices: listingData.prices || [],
      cpkPrices: cpkData.prices || [],
    });
  } catch (error) {
    console.error(`Error fetching price history for ${listingId}:`, error);
    return NextResponse.json(
      { error: "Internal server error", details: String(error) },
      { status: 500 }
    );
  }
}
