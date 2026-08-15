"use client";

import { X } from "lucide-react";
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
  listingPrices: PriceObservation[];
  cpkPrices?: PriceObservation[];
  onClose: () => void;
}

export function PriceHistoryModal({
  listingId,
  listingPrices,
  cpkPrices,
  onClose,
}: PriceHistoryModalProps) {
  // Sort by date for chart
  const sortedListing = [...listingPrices].sort(
    (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
  );

  const sortedCpk = cpkPrices
    ? [...cpkPrices].sort(
        (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
      )
    : [];

  // Format for Recharts - align both datasets by timestamp
  const timestamps = new Set<number>();
  sortedListing.forEach((p) =>
    timestamps.add(new Date(p.observed_at).getTime())
  );
  sortedCpk.forEach((p) => timestamps.add(new Date(p.observed_at).getTime()));

  const sortedTimestamps = Array.from(timestamps).sort((a, b) => a - b);
  const listingMap = new Map(
    sortedListing.map((p) => [
      new Date(p.observed_at).getTime(),
      p.delivered_price,
    ])
  );
  const cpkMap = new Map(
    sortedCpk.map((p) => [
      new Date(p.observed_at).getTime(),
      p.delivered_price,
    ])
  );

  const chartData = sortedTimestamps.map((ts) => ({
    timestamp: ts,
    date: new Date(ts).toLocaleDateString("en-GB", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 border border-slate-600 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-600">
          <h2 className="text-lg font-semibold text-slate-100">Price History</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition"
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
              <div className="grid grid-cols-2 gap-3 mb-6">
                <div className="bg-slate-700 rounded p-3 border-l-2 border-blue-400">
                  <div className="text-xs text-slate-400">This Listing</div>
                  <div className="text-lg font-semibold text-blue-300 mb-1">
                    £{currentListingPrice.toFixed(2)}
                  </div>
                  <div className="text-xs text-slate-400">
                    Avg: £{avgListingPrice.toFixed(2)} | Min: £
                    {minListingPrice.toFixed(2)} | Max: £
                    {maxListingPrice.toFixed(2)}
                  </div>
                </div>
                {cpkPrices && cpkPrices.length > 0 && (
                  <div className="bg-slate-700 rounded p-3 border-l-2 border-orange-400">
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
                <div className="mb-6 p-3 bg-slate-700 rounded">
                  <div className="text-xs text-slate-400 mb-1">vs Market</div>
                  <div className="flex items-baseline gap-2">
                    <span className={`text-sm font-semibold ${
                      priceVsMarket < 0 ? "text-green-400" : "text-red-400"
                    }`}>
                      {priceVsMarket < 0 ? "↓" : "↑"} £{Math.abs(priceVsMarket).toFixed(2)}
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
              <div className="mb-6 p-3 bg-slate-700 rounded">
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
              <div className="bg-slate-750 rounded p-4 border border-slate-600">
                <ResponsiveContainer width="100%" height={300}>
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
