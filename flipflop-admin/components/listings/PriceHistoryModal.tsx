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
  prices: PriceObservation[];
  onClose: () => void;
}

export function PriceHistoryModal({
  listingId,
  prices,
  onClose,
}: PriceHistoryModalProps) {
  // Sort by date for chart
  const sorted = [...prices].sort(
    (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
  );

  // Format for Recharts
  const chartData = sorted.map((obs) => ({
    timestamp: new Date(obs.observed_at),
    date: new Date(obs.observed_at).toLocaleDateString("en-GB", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
    price: obs.delivered_price,
  }));

  const minPrice = Math.min(...sorted.map((p) => p.delivered_price));
  const maxPrice = Math.max(...sorted.map((p) => p.delivered_price));
  const avgPrice = sorted.reduce((sum, p) => sum + p.delivered_price, 0) / sorted.length;
  const currentPrice = sorted[sorted.length - 1]?.delivered_price ?? 0;
  const priceChange = currentPrice - (sorted[0]?.delivered_price ?? 0);

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
          {prices.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-slate-400">
              No price history available
            </div>
          ) : (
            <>
              {/* Stats */}
              <div className="grid grid-cols-4 gap-3 mb-6">
                <div className="bg-slate-700 rounded p-3">
                  <div className="text-xs text-slate-400">Current</div>
                  <div className="text-lg font-semibold text-slate-100">
                    £{currentPrice.toFixed(2)}
                  </div>
                </div>
                <div className="bg-slate-700 rounded p-3">
                  <div className="text-xs text-slate-400">Average</div>
                  <div className="text-lg font-semibold text-slate-100">
                    £{avgPrice.toFixed(2)}
                  </div>
                </div>
                <div className="bg-slate-700 rounded p-3">
                  <div className="text-xs text-slate-400">Min</div>
                  <div className="text-lg font-semibold text-green-400">
                    £{minPrice.toFixed(2)}
                  </div>
                </div>
                <div className="bg-slate-700 rounded p-3">
                  <div className="text-xs text-slate-400">Max</div>
                  <div className="text-lg font-semibold text-red-400">
                    £{maxPrice.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Trend */}
              <div className="mb-6 p-3 bg-slate-700 rounded">
                <div className="text-xs text-slate-400">Trend</div>
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-semibold text-slate-100">
                    {priceChange < 0 ? "↓" : priceChange > 0 ? "↑" : "→"}{" "}
                    £{Math.abs(priceChange).toFixed(2)}
                  </span>
                  <span className={`text-xs ${
                    priceChange < 0 ? "text-green-400" : priceChange > 0 ? "text-red-400" : "text-slate-400"
                  }`}>
                    {priceChange < 0 ? "Dropped" : priceChange > 0 ? "Increased" : "Stable"}
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
                      formatter={(value) => [`£${Number(value).toFixed(2)}`, "Price"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="price"
                      stroke={priceChange < 0 ? "#10b981" : priceChange > 0 ? "#ef4444" : "#6b7280"}
                      dot={{ fill: "#6b7280", r: 4 }}
                      activeDot={{ r: 6 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Observations Count */}
              <div className="mt-4 text-xs text-slate-400 text-center">
                {prices.length} observation{prices.length !== 1 ? "s" : ""} over{" "}
                {Math.ceil(
                  (new Date(sorted[sorted.length - 1].observed_at).getTime() -
                    new Date(sorted[0].observed_at).getTime()) /
                    (1000 * 60 * 60 * 24)
                )}{" "}
                days
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
