"use client";

import { useState } from "react";
import { ManualBuild, CourierQuote, api } from "@/lib/api";
import { Package, Loader2, AlertCircle, MapPin, Truck, CheckCircle2, ExternalLink } from "lucide-react";

interface Props {
  build: ManualBuild;
  onRefresh: () => Promise<void>;
}

export function EbayShipmentBookingSection({ build, onRefresh }: Props) {
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const [quotes, setQuotes] = useState<CourierQuote[]>([]);
  const [selectedQuoteIndex, setSelectedQuoteIndex] = useState(0);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const quote = quotes[selectedQuoteIndex] ?? null;

  const [booking, setBooking] = useState(false);
  const [bookError, setBookError] = useState<string | null>(null);
  const [bookWarning, setBookWarning] = useState<string | null>(null);

  const handleSync = async () => {
    setSyncing(true);
    setSyncError(null);
    try {
      await api.manualBuilds.syncEbayOrder(build.id);
      await onRefresh();
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Failed to sync eBay order");
    } finally {
      setSyncing(false);
    }
  };

  const handleGetQuote = async () => {
    setLoadingQuote(true);
    setQuoteError(null);
    setQuotes([]);
    setSelectedQuoteIndex(0);
    try {
      const result = await api.manualBuilds.getCourierQuote(build.id);
      setQuotes(result);
    } catch (error) {
      setQuoteError(error instanceof Error ? error.message : "Failed to get courier quote");
    } finally {
      setLoadingQuote(false);
    }
  };

  const handleBook = async () => {
    if (!quote?.service_slug) return;
    setBooking(true);
    setBookError(null);
    setBookWarning(null);
    try {
      const result = await api.manualBuilds.bookShipment(build.id, {
        service_slug: quote.service_slug,
        price_gbp: quote.price_gbp,
      });
      if (!result.success) {
        setBookError(result.error ?? "Booking failed");
      } else if (result.warning) {
        setBookWarning(result.warning);
      }
      await onRefresh();
    } catch (error) {
      setBookError(error instanceof Error ? error.message : "Failed to book shipment");
    } finally {
      setBooking(false);
    }
  };

  // Only relevant once the build has actually been posted to eBay — sync
  // itself is what confirms whether it's sold yet, so this can't gate on
  // build.status === "sold" (that status is only set BY a successful sync).
  if (!build.ebay_listing_id) return null;

  const hasBuyerAddress = Boolean(build.buyer_address_json);
  const alreadyBooked = Boolean(build.tracking_number);
  const address = build.buyer_address_json;

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3 mb-6">
      <p className="text-sm font-semibold flex items-center gap-2">
        <Truck className="w-4 h-4 text-slate-500" /> Real Shipment
      </p>

      {!hasBuyerAddress ? (
        <>
          <p className="text-[11px] text-slate-500">
            Fetch the real buyer address and sale price from eBay&apos;s order — only available once this build
            has actually sold.
          </p>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-black rounded-lg transition-colors"
          >
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
            {syncing ? "Checking…" : "Sync eBay Order"}
          </button>
          {syncError && (
            <div className="flex items-start gap-2 p-2 rounded bg-red-900/20 border border-red-700/40">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-xs text-red-300">{syncError}</p>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-lg bg-black/20 border border-white/[0.07] p-3 text-xs space-y-1">
          <p className="text-slate-300 font-semibold">{build.buyer_name}</p>
          <p className="text-slate-500">
            {[address?.address_line1, address?.address_line2, address?.city, address?.postal_code]
              .filter(Boolean)
              .join(", ")}
          </p>
          <p className="text-slate-500">Sold for £{build.sale_price_actual?.toFixed(2)}</p>
        </div>
      )}

      {hasBuyerAddress && alreadyBooked && (
        <div className="rounded-lg bg-emerald-950/40 border border-emerald-700/50 p-3 text-xs space-y-1">
          <p className="flex items-center gap-1.5 text-emerald-100 font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5" /> Shipment booked
          </p>
          <p className="text-emerald-300">Tracking: {build.tracking_number}</p>
          {build.shipping_label_url && (
            <a
              href={build.shipping_label_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-emerald-300 underline"
            >
              <ExternalLink className="w-3 h-3" /> View label
            </a>
          )}
        </div>
      )}

      {hasBuyerAddress && !alreadyBooked && (
        <>
          <button
            onClick={handleGetQuote}
            disabled={loadingQuote}
            className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-slate-700 hover:bg-slate-600 disabled:opacity-60 text-slate-200 rounded-lg transition-colors"
          >
            {loadingQuote ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
            {loadingQuote ? "Getting quote…" : "Get Courier Quote (real address)"}
          </button>

          {quoteError && (
            <div className="flex items-start gap-2 p-2 rounded bg-red-900/20 border border-red-700/40">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-xs text-red-300">{quoteError}</p>
            </div>
          )}

          {quote && (
            <div className="space-y-2 p-3 rounded bg-amber-950/30 border border-amber-700/40">
              {quotes.length > 1 && (
                <label className="block text-xs text-slate-300">
                  <span className="mb-1 block font-semibold">Courier service</span>
                  <select
                    value={selectedQuoteIndex}
                    onChange={(event) => setSelectedQuoteIndex(Number(event.target.value))}
                    className="w-full rounded border border-white/10 bg-slate-900 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-400"
                  >
                    {quotes.map((option, index) => (
                      <option key={`${option.service_slug}-${index}`} value={index}>
                        {index === 0 ? "Cheapest · " : ""}{option.courier_name} — {option.service_name} — £{option.price_gbp.toFixed(2)}{option.estimated_days != null ? ` · ${option.estimated_days} day est.` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p className="text-xs text-amber-100 font-semibold">
                {quote.courier_name} — {quote.service_name}: £{quote.price_gbp.toFixed(2)}
              </p>
              <p className="text-[10px] text-amber-300/80">
                Booking charges your Parcel2Go account immediately and can&apos;t be undone automatically.
              </p>
              <button
                onClick={handleBook}
                disabled={booking || !quote.service_slug}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-amber-600 hover:bg-amber-500 disabled:opacity-60 text-black rounded-lg transition-colors"
              >
                {booking ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {booking ? "Booking…" : `Book & Pay — £${quote.price_gbp.toFixed(2)} via Parcel2Go`}
              </button>
            </div>
          )}

          {bookError && (
            <div className="flex items-start gap-2 p-2 rounded bg-red-900/20 border border-red-700/40">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-xs text-red-300">{bookError}</p>
            </div>
          )}
          {bookWarning && (
            <div className="flex items-start gap-2 p-2 rounded bg-amber-900/20 border border-amber-700/40">
              <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-xs text-amber-300">{bookWarning}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
