"use client";

import { useEffect, useState } from "react";
import { Gavel, Timer } from "lucide-react";
import { Listing } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

/** Live countdown for an auction end time — updates every second. */
export function useCountdown(endsAt: string | null): string {
  const [label, setLabel] = useState("");
  useEffect(() => {
    if (!endsAt) return;
    const update = () => {
      const diff = new Date(endsAt).getTime() - Date.now();
      if (diff <= 0) { setLabel("Ended"); return; }
      const d = Math.floor(diff / 86_400_000);
      const h = Math.floor((diff % 86_400_000) / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1_000);
      if (d > 0)      setLabel(`${d}d ${h}h`);
      else if (h > 0) setLabel(`${h}h ${m}m`);
      else            setLabel(`${m}m ${s}s`);
    };
    update();
    const id = setInterval(update, 1_000);
    return () => clearInterval(id);
  }, [endsAt]);
  return label;
}

/** Gavel icon + live countdown; only renders for auction listings. */
export function AuctionBadge({ listing }: { listing: Listing }) {
  const countdown = useCountdown(listing.listing_ends_at);
  if (listing.listing_type !== "auction") return null;
  const ended = countdown === "Ended";
  return (
    <div
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold border ${
        ended
          ? "bg-slate-800/60 border-slate-700 text-slate-500"
          : "bg-amber-400/10 border-amber-400/30 text-amber-400"
      }`}
    >
      <Gavel className="w-2.5 h-2.5" />
      {ended ? "Ended" : (
        <>
          <Timer className="w-2.5 h-2.5" />
          {countdown || "Auction"}
        </>
      )}
    </div>
  );
}

/**
 * For auction listings: shows muted current bid + amber expected hammer price.
 * For BIN / classified: shows plain price.
 */
export function AuctionPriceDisplay({ listing }: { listing: Listing }) {
  if (listing.listing_type !== "auction") {
    return (
      <span className="text-sm font-bold text-slate-200">
        {formatCurrency(listing.price)}
      </span>
    );
  }
  const hasForecast =
    listing.expected_buy_price && listing.expected_buy_price !== listing.price;
  return (
    <div>
      <div className="text-[10px] text-slate-600">Bid: {formatCurrency(listing.price)}</div>
      {hasForecast ? (
        <div
          className="text-sm font-bold text-amber-400"
          title="Estimated final hammer price from completed eBay auction comps"
        >
          ~{formatCurrency(listing.expected_buy_price!)}
        </div>
      ) : (
        <span className="text-sm font-bold text-slate-200">
          {formatCurrency(listing.price)}
        </span>
      )}
    </div>
  );
}
