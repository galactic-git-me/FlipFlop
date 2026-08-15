import { NextResponse } from "next/server";

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

export async function GET(
  request: Request,
  { params }: { params: { listingId: string } }
) {
  const { listingId } = params;

  if (!listingId) {
    return NextResponse.json(
      { error: "Listing ID is required" },
      { status: 400 }
    );
  }

  try {
    // Call the backend API to get price history
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(
      `${backendUrl}/api/gem_radar/listings/${encodeURIComponent(listingId)}/price-history`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch price history from backend" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({
      prices: data.prices || [],
    });
  } catch (error) {
    console.error(`Error fetching price history for ${listingId}:`, error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
