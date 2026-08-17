"use client";

import { useEffect } from "react";
import { TrendingDown, TrendingUp, X } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

interface PriceHistoryModalProps {
  listingId: string;
  listingTitle?: string;
  listingPrices: PriceObservation[];
  cpkPrices?: PriceObservation[];
  onClose: () => void;
}

export function PriceHistoryModal({
  listingId,
  listingTitle,
  listingPrices,
  cpkPrices,
  onClose,
}: PriceHistoryModalProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", closeOnEscape);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  // Sort by date for chart
  const sortedListing = [...listingPrices].sort(
    (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
  );

  const sortedCpk = cpkPrices
    ? [...cpkPrices].sort(
        (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
      )
    : [];

  // Align both series to calendar days. The market endpoint is daily and a
  // listing can be observed multiple times per day; the latest listing value
  // for each day is the most useful like-for-like comparison.
  const dayKey = (value: string) => {
    const date = new Date(value);
    date.setHours(0, 0, 0, 0);
    return date.getTime();
  };
  const timestamps = new Set<number>();
  sortedListing.forEach((p) => timestamps.add(dayKey(p.observed_at)));
  sortedCpk.forEach((p) => timestamps.add(dayKey(p.observed_at)));

  const sortedTimestamps = Array.from(timestamps).sort((a, b) => a - b);
  const listingMap = new Map(
    sortedListing.map((p) => [
      dayKey(p.observed_at),
      p.delivered_price,
    ])
  );
  const cpkMap = new Map(
    sortedCpk.map((p) => [
      dayKey(p.observed_at),
      p.delivered_price,
    ])
  );

  const chartData = sortedTimestamps.map((ts) => ({
    timestamp: ts,
    date: new Date(ts).toLocaleDateString("en-GB", {
      month: "short",
      day: "numeric",
    }),
    listingPrice: listingMap.get(ts),
    cpkPrice: cpkMap.get(ts),
  }));

  // Stats for listing prices
  const listingPriceValues = sortedListing.map((p) => p.delivered_price);
  const minListingPrice = Math.min(...listingPriceValues);
  const maxListingPrice = Math.max(...listingPriceValues);
  const avgListingPrice =
    listingPriceValues.reduce((sum, p) => sum + p, 0) / listingPriceValues.length;
  const currentListingPrice = sortedListing[sortedListing.length - 1]?.delivered_price ?? 0;
  const listingPriceChange = currentListingPrice - (sortedListing[0]?.delivered_price ?? 0);

  // Stats for CPK prices
  const cpkPriceValues = sortedCpk.map((p) => p.delivered_price);
  const currentCpkPrice =
    sortedCpk[sortedCpk.length - 1]?.delivered_price ?? 0;
  const avgCpkPrice =
    cpkPriceValues.length > 0
      ? cpkPriceValues.reduce((sum, p) => sum + p, 0) / cpkPriceValues.length
      : 0;

  // Premium/discount vs market
  const priceVsMarket = currentListingPrice - currentCpkPrice;
  const percentVsMarket =
    currentCpkPrice > 0
      ? ((currentListingPrice - currentCpkPrice) / currentCpkPrice) * 100
      : 0;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/80 p-3 backdrop-blur-sm" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="price-history-title" className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-600 bg-slate-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-600">
          <div className="min-w-0"><h2 id="price-history-title" className="text-lg font-semibold text-slate-100">Price history</h2><p className="truncate text-xs text-slate-400">{listingTitle || `Listing ${listingId}`}</p></div>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            aria-label="Close price history"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {listingPrices.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-slate-400">
              No price history available
            </div>
          ) : (
            <>
              {/* Stats */}
              <div className="mb-6 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-blue-400/30 bg-blue-500/10 p-4">
                  <div className="text-xs text-slate-400">This Listing</div>
                  <div className="text-lg font-semibold text-blue-300 mb-1">
                    £{currentListingPrice.toFixed(2)}
                  </div>
                  <div className="text-xs text-slate-400">Average £{avgListingPrice.toFixed(2)} · Range £{minListingPrice.toFixed(2)}–£{maxListingPrice.toFixed(2)}</div>
                </div>
                {cpkPrices && cpkPrices.length > 0 && (
                  <div className="rounded-xl border border-orange-400/30 bg-orange-500/10 p-4">
                    <div className="text-xs text-slate-400">Market CPK Average</div>
                    <div className="text-lg font-semibold text-orange-300 mb-1">
                      £{currentCpkPrice.toFixed(2)}
                    </div>
                    <div className="text-xs text-slate-400">
                      Avg: £{avgCpkPrice.toFixed(2)}
                    </div>
                  </div>
                )}
              </div>

              {/* vs Market */}
              {cpkPrices && cpkPrices.length > 0 && (
                <div className="mb-6 rounded-xl border border-slate-700 bg-slate-800 p-4">
                  <div className="text-xs text-slate-400 mb-1">vs Market</div>
                  <div className="flex items-baseline gap-2">
                    <span className={`text-sm font-semibold ${
                      priceVsMarket < 0 ? "text-green-400" : "text-red-400"
                    }`}>
                      {priceVsMarket < 0 ? <TrendingDown className="inline h-4 w-4" /> : <TrendingUp className="inline h-4 w-4" />} £{Math.abs(priceVsMarket).toFixed(2)}
                    </span>
                    <span className={`text-xs ${
                      priceVsMarket < 0 ? "text-green-400" : "text-red-400"
                    }`}>
                      ({priceVsMarket < 0 ? "-" : "+"}{percentVsMarket.toFixed(1)}%)
                    </span>
                  </div>
                </div>
              )}

              {/* Trend */}
              <div className="mb-6 rounded-xl border border-slate-700 bg-slate-800 p-4">
                <div className="text-xs text-slate-400">Trend (This Listing)</div>
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-semibold text-slate-100">
                    {listingPriceChange < 0 ? "↓" : listingPriceChange > 0 ? "↑" : "→"}{" "}
                    £{Math.abs(listingPriceChange).toFixed(2)}
                  </span>
                  <span
                    className={`text-xs ${
                      listingPriceChange < 0
                        ? "text-green-400"
                        : listingPriceChange > 0
                          ? "text-red-400"
                          : "text-slate-400"
                    }`}
                  >
                    {listingPriceChange < 0
                      ? "Dropped"
                      : listingPriceChange > 0
                        ? "Increased"
                        : "Stable"}
                  </span>
                </div>
              </div>

              {/* Chart */}
              <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3 sm:p-5">
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                    <XAxis
                      dataKey="date"
                      stroke="#94a3b8"
                      style={{ fontSize: "12px" }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      style={{ fontSize: "12px" }}
                      label={{ value: "Price (£)", angle: -90, position: "insideLeft" }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1e293b",
                        border: "1px solid #475569",
                        borderRadius: "6px",
                      }}
                      labelStyle={{ color: "#e2e8f0" }}
                      formatter={(value) => [`£${Number(value).toFixed(2)}`]}
                      labelFormatter={(label) => label}
                    />
                    <Line
                      type="monotone"
                      dataKey="listingPrice"
                      stroke="#3b82f6"
                      dot={false}
                      activeDot={{ r: 6 }}
                      isAnimationActive={false}
                      name="This Listing"
                      strokeWidth={2}
                      connectNulls
                    />
                    {sortedCpk.length > 0 && (
                      <Line
                        type="monotone"
                        dataKey="cpkPrice"
                        stroke="#f97316"
                        dot={false}
                        activeDot={{ r: 6 }}
                        isAnimationActive={false}
                        name="Market CPK"
                        strokeWidth={2}
                        opacity={0.7}
                        connectNulls
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Legend */}
              <div className="mt-3 flex gap-4 justify-center text-xs">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-blue-400"></div>
                  <span className="text-slate-300">This Listing</span>
                </div>
                {sortedCpk.length > 0 && (
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-orange-400"></div>
                    <span className="text-slate-300">Market CPK</span>
                  </div>
                )}
              </div>

              {/* Observations Count */}
              <div className="mt-4 text-xs text-slate-400 text-center">
                {listingPrices.length} listing observation
                {listingPrices.length !== 1 ? "s" : ""}
                {sortedCpk.length > 0 && ` | ${sortedCpk.length} CPK observation${sortedCpk.length !== 1 ? "s" : ""}`}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
